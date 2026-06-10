"""Fish Speech TTS engine wrapper — subprocess client.

Fish Speech lives in its OWN venv (fish_speech_env/), not the server venv, so
importing it here can never work. Instead this wrapper manages a persistent
worker process (scripts/fish_server.py) that loads the model once and serves
synthesis over local HTTP. Gracefully degrades: is_available() is False when
the env/checkpoints/reference are missing, and synthesize() returns None on
any failure so the TTS router falls through to the next engine.

Usage:
    tts = FishSpeechTTS(reference_audio="characters/x/voice/reference_audio.wav",
                        ref_text="transcript of the reference",
                        params={"temperature": 0.9})
    if tts.is_available():
        audio_bytes = tts.synthesize_sync("Hello there!")
"""

import logging
import os
import subprocess
import time

logger = logging.getLogger(__name__)

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FISH_PY = os.path.join(_BASE, "fish_speech_env", "Scripts", "python.exe")
_FISH_SERVER = os.path.join(_BASE, "scripts", "fish_server.py")
_FISH_CKPT = os.path.join(_BASE, "fish_speech_ckpts",
                          "firefly-gan-vq-fsq-8x1024-21hz-generator.pth")
_PORT = int(os.environ.get("FISH_PORT", "7861"))
_STARTUP_TIMEOUT = 240  # first start includes full model load


class FishSpeechTTS:
    """Voice-cloning TTS via a persistent Fish Speech worker subprocess."""

    engine_name = "fish_speech"

    def __init__(self, reference_audio: str, ref_text: str = "", params: dict = None,
                 device: str = "cuda"):
        # Prefer the longer "clean" reference if it exists next to the standard
        # one — Fish handles long references well (unlike SoVITS's 3-10s limit).
        ref = reference_audio or ""
        if ref:
            clean = os.path.join(os.path.dirname(ref), "reference_clean.wav")
            if os.path.isfile(clean):
                ref = clean
        self._ref = os.path.abspath(ref) if ref else ""
        self._ref_text = ref_text or self._load_ref_text(reference_audio)
        self._params = params or {}
        self._proc = None

    @staticmethod
    def _load_ref_text(reference_audio: str) -> str:
        if not reference_audio:
            return ""
        p = os.path.join(os.path.dirname(reference_audio), "reference_text.txt")
        try:
            with open(p, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            return ""

    def is_available(self) -> bool:
        return (os.path.isfile(_FISH_PY) and os.path.isfile(_FISH_SERVER)
                and os.path.isfile(_FISH_CKPT)
                and bool(self._ref) and os.path.isfile(self._ref))

    # ── worker management ────────────────────────────────────────────────────
    def _health(self, timeout=2.0) -> bool:
        import httpx
        try:
            r = httpx.get(f"http://127.0.0.1:{_PORT}/health", timeout=timeout)
            return r.status_code == 200
        except Exception:
            return False

    def _ensure_server(self) -> bool:
        if self._health():
            return True
        if self._proc is not None and self._proc.poll() is not None:
            self._proc = None
        if self._proc is None:
            logger.info("[fish_speech_tts] starting fish_server worker...")
            self._proc = subprocess.Popen(
                [_FISH_PY, _FISH_SERVER, str(_PORT)],
                cwd=_BASE,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        deadline = time.time() + _STARTUP_TIMEOUT
        while time.time() < deadline:
            if self._health():
                logger.info("[fish_speech_tts] fish_server ready")
                return True
            if self._proc.poll() is not None:
                logger.warning("[fish_speech_tts] fish_server died during startup")
                self._proc = None
                return False
            time.sleep(3)
        logger.warning("[fish_speech_tts] fish_server startup timed out")
        return False

    # ── synthesis ────────────────────────────────────────────────────────────
    def synthesize_sync(self, text: str, rate: str = None, pitch: str = None,
                        nocache: bool = False, **kwargs) -> bytes | None:
        """Synchronous interface matching the TTSRouter engine contract."""
        if not self.is_available() or not text or not text.strip():
            return None
        try:
            if not self._ensure_server():
                return None
            import httpx
            payload = {
                "text": text, "ref": self._ref, "ref_text": self._ref_text,
                "temperature": self._params.get("temperature", 0.9),
                "top_p": self._params.get("top_p", 0.85),
                "repetition_penalty": self._params.get("repetition_penalty", 1.4),
            }
            r = httpx.post(f"http://127.0.0.1:{_PORT}/synthesize",
                           json=payload, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                return r.content
            logger.warning(f"[fish_speech_tts] synthesize failed: HTTP {r.status_code}")
        except Exception as e:
            logger.warning(f"[fish_speech_tts] synthesize error: {e}")
        return None

    async def synthesize(self, text: str, rate: str = None, pitch: str = None,
                         output_path: str = None, **kwargs) -> bytes | None:
        import asyncio
        data = await asyncio.to_thread(self.synthesize_sync, text)
        if data and output_path:
            with open(output_path, "wb") as f:
                f.write(data)
        return data

    def shutdown(self):
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            self._proc = None
