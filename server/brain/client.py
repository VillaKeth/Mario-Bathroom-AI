"""Server-side handle on the brain subprocess (JSON lines over stdio).

Never blocks the event loop on the brain: a reader thread parses the worker's
stdout and resolves per-request futures on the loop. A hung or dead worker
costs one window (run() returns None -> the fly does nothing) and is restarted
on a later call, at most once per restart_cooldown seconds. Written after the
GPT-SoVITS client in server/tts.py, minus its quit-key bug (it sends
{"command": "quit"} while the server reads "cmd").
"""
import asyncio
import json
import logging
import subprocess
import threading
import time

logger = logging.getLogger(__name__)


class BrainClient:
    def __init__(self, cmd, cwd=None, env=None, request_timeout=10.0, restart_cooldown=30.0):
        self.cmd = list(cmd)
        self.cwd = cwd
        self.env = env
        self.request_timeout = float(request_timeout)
        self.restart_cooldown = float(restart_cooldown)
        self.status = "stopped"          # stopped | loading | ready | offline
        self.stage = ""
        self.progress = 0.0
        self.info = {}
        self.error = ""
        self._proc = None
        self._loop = None
        self._pending = {}
        self._next_id = 1
        self._last_spawn = float("-inf")

    async def start(self):
        self._loop = asyncio.get_running_loop()
        self._spawn()

    def _spawn(self):
        self._last_spawn = time.monotonic()
        self.status, self.stage, self.progress, self.error = "loading", "spawn", 0.0, ""
        try:
            proc = subprocess.Popen(self.cmd, cwd=self.cwd, env=self.env,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                    errors="replace", bufsize=1)
        except OSError as e:
            self.status, self.error = "offline", f"spawn failed: {e}"
            logger.error(f"[BRAIN] {self.error}")
            return
        self._proc = proc
        threading.Thread(target=self._read_stdout, args=(proc,), daemon=True,
                         name="brain-stdout").start()
        threading.Thread(target=self._drain_stderr, args=(proc,), daemon=True,
                         name="brain-stderr").start()

    def _read_stdout(self, proc):
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            self._post(self._on_msg, proc, msg)
        self._post(self._on_exit, proc)

    def _drain_stderr(self, proc):
        for line in proc.stderr:
            line = line.rstrip()
            if line:
                logger.info(f"[BRAIN worker] {line}")

    def _post(self, fn, *args):
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(fn, *args)
        except RuntimeError:
            pass  # loop shutting down

    def _on_msg(self, proc, msg):
        if proc is not self._proc:
            return
        status = msg.get("status")
        if status == "loading":
            self.stage = str(msg.get("stage", ""))
            self.progress = float(msg.get("progress") or 0.0)
        elif status == "ready":
            self.status, self.progress, self.info = "ready", 1.0, msg
            logger.info(f"[BRAIN] ready: {msg.get('neurons')} neurons, "
                        f"{msg.get('connections')} connections")
        elif msg.get("id") is not None:
            fut = self._pending.pop(msg["id"], None)
            if fut is not None and not fut.done():
                fut.set_result(msg)
        elif status == "error":
            self.error = str(msg.get("error", ""))
            logger.error(f"[BRAIN] worker error: {self.error}")

    def _on_exit(self, proc):
        if proc is not self._proc:
            return
        if self.status != "stopped":
            self.status = "offline"
            logger.warning(f"[BRAIN] worker exited (code {proc.poll()}) {self.error}")
        self._fail_pending()

    def _fail_pending(self):
        pending, self._pending = self._pending, {}
        for fut in pending.values():
            if not fut.done():
                fut.set_result(None)

    def _kill(self):
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        self.status = "offline"
        self._fail_pending()

    async def run(self, stim, ms=500, seed=0, noise=None, reset=False):
        if self.status == "offline":
            if time.monotonic() - self._last_spawn >= self.restart_cooldown:
                logger.info("[BRAIN] restarting worker")
                self._spawn()
            return None
        if self.status != "ready" or self._proc is None:
            return None
        rid = self._next_id
        self._next_id += 1
        fut = self._loop.create_future()
        self._pending[rid] = fut
        req = {"cmd": "run", "id": rid, "ms": ms, "seed": int(seed), "stim": list(stim or []),
               "noise": noise or {"frac": 0.0, "rate": 0.0}, "reset": bool(reset)}
        try:
            self._proc.stdin.write(json.dumps(req) + "\n")
            self._proc.stdin.flush()
        except (OSError, ValueError) as e:
            logger.warning(f"[BRAIN] write failed: {e}")
            self._pending.pop(rid, None)
            self._kill()
            return None
        try:
            msg = await asyncio.wait_for(fut, self.request_timeout)
        except asyncio.TimeoutError:
            logger.warning(f"[BRAIN] window timed out after {self.request_timeout}s; killing worker")
            self._pending.pop(rid, None)
            self._kill()
            return None
        if not msg or msg.get("status") != "ok":
            if msg:
                logger.warning(f"[BRAIN] run failed: {msg.get('error')}")
            return None
        return msg

    async def stop(self):
        proc, self._proc = self._proc, None
        self.status = "stopped"
        self._fail_pending()
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
            proc.stdin.flush()
        except (OSError, ValueError):
            pass
        for _ in range(30):
            if proc.poll() is not None:
                return
            await asyncio.sleep(0.1)
        try:
            proc.kill()
        except OSError:
            pass
