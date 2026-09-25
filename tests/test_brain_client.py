import asyncio
import sys

import pytest

from server.brain.client import BrainClient

FAKE = r'''
import json, sys, time
mode = sys.argv[1]
print(json.dumps({"status": "loading", "stage": "load", "progress": 0.5}), flush=True)
if mode == "die":
    sys.exit(3)
print(json.dumps({"status": "ready", "neurons": 3, "order": [], "populations": {}}), flush=True)
for line in sys.stdin:
    req = json.loads(line)
    if req.get("cmd") == "quit":
        break
    if mode == "hang":
        time.sleep(60)
    if mode == "crash":
        sys.exit(1)
    print(json.dumps({"status": "ok", "id": req["id"], "rates": {"feed": 99.0},
                      "stim": req["stim"], "noise": req["noise"]}), flush=True)
'''


async def _until(pred, timeout=15.0):
    for _ in range(int(timeout / 0.05)):
        if pred():
            return True
        await asyncio.sleep(0.05)
    return False


@pytest.fixture
def fake(tmp_path):
    p = tmp_path / "fake_worker.py"
    p.write_text(FAKE, encoding="utf-8")
    return lambda mode: [sys.executable, str(p), mode]


async def test_ready_then_run(fake):
    c = BrainClient(fake("ok"))
    await c.start()
    assert await _until(lambda: c.status == "ready")
    assert c.info["neurons"] == 3
    r = await c.run([{"pop": "sugar", "rate": 150, "side": "both"}], ms=100, seed=1)
    assert r["rates"]["feed"] == 99.0
    assert r["stim"][0]["pop"] == "sugar" and r["noise"] == {"frac": 0.0, "rate": 0.0}
    await c.stop()
    assert c.status == "stopped"


async def test_run_while_loading_returns_none(fake):
    c = BrainClient(fake("ok"))
    await c.start()
    assert c.status == "loading"
    assert await c.run([], ms=100) is None
    await c.stop()


async def test_hang_times_out_and_kills(fake):
    c = BrainClient(fake("hang"), request_timeout=0.5, restart_cooldown=999)
    await c.start()
    assert await _until(lambda: c.status == "ready")
    assert await c.run([], ms=100) is None
    assert c.status == "offline"
    await c.stop()


async def test_crash_goes_offline_then_restarts(fake):
    c = BrainClient(fake("crash"), restart_cooldown=0.0)
    await c.start()
    assert await _until(lambda: c.status == "ready")
    assert await c.run([], ms=100) is None
    assert await _until(lambda: c.status == "offline")
    assert await c.run([], ms=100) is None  # triggers the restart
    assert await _until(lambda: c.status == "ready")
    await c.stop()


async def test_worker_dying_at_start_is_offline(fake):
    c = BrainClient(fake("die"), restart_cooldown=999)
    await c.start()
    assert await _until(lambda: c.status == "offline")
    assert await c.run([], ms=100) is None
    await c.stop()
