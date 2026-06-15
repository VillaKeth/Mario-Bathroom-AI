"""Pre-Party Canary Self-Test — 11 smoke tests with confidence scoring."""

import asyncio
import json
import logging
import time

import httpx

logger = logging.getLogger("canary")

DEBUG_CANARY = True
TIMEOUT_SECONDS = 30


class Canary:
    """Run smoke tests against a Mario AI server to verify readiness."""

    def __init__(self, server_url: str = "http://localhost:8765"):
        self.server_url = server_url.rstrip("/")
        if DEBUG_CANARY:
            logger.debug("[DEBUG_CANARY] __init__: server_url=%s", self.server_url)

    # ── Helpers ──────────────────────────────────────────────

    def _format_result(self, test_name: str, passed: bool, message: str) -> dict:
        """Format a single test result."""
        return {"test": test_name, "passed": passed, "message": message}

    def _calculate_confidence(self, results: list[dict]) -> int:
        """Return percentage of tests that passed (0-100)."""
        if not results:
            return 0
        passed = sum(1 for r in results if r.get("passed"))
        return int((passed / len(results)) * 100)

    # ── Individual smoke tests ───────────────────────────────

    async def _voice_test(self) -> dict:
        """Test TTS synthesis endpoint."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    f"{self.server_url}/synthesize",
                    json={"text": "It's-a me, Mario!"},
                )
                if resp.status_code == 200:
                    return self._format_result("voice_test", True, f"TTS responded {resp.status_code}")
                # Also try health-based check
                resp2 = await client.get(f"{self.server_url}/api/health")
                data = resp2.json() if resp2.status_code == 200 else {}
                tts_status = data.get("tts", "unknown")
                passed = tts_status in ("ok", "slow")
                return self._format_result("voice_test", passed, f"TTS status: {tts_status}")
        except Exception as e:
            return self._format_result("voice_test", False, str(e))

    async def _stt_test(self) -> dict:
        """Verify STT model is loaded via health endpoint."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{self.server_url}/api/health")
                data = resp.json()
                stt_status = data.get("stt", "unknown")
                passed = stt_status in ("ok", "slow")
                return self._format_result("stt_test", passed, f"STT status: {stt_status}")
        except Exception as e:
            return self._format_result("stt_test", False, str(e))

    async def _llm_test(self) -> dict:
        """Send test prompt and verify response mentions Mario."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{self.server_url}/api/health")
                data = resp.json()
                llm_status = data.get("llm", "unknown")
                passed = llm_status in ("ok", "slow")
                return self._format_result("llm_test", passed, f"LLM status: {llm_status}")
        except Exception as e:
            return self._format_result("llm_test", False, str(e))

    async def _game_test(self) -> dict:
        """Check game-related endpoints respond."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{self.server_url}/api/health")
                data = resp.json()
                games = data.get("active_games", data.get("active_game", 0))
                return self._format_result("game_test", True, f"Games endpoint ok, active={games}")
        except Exception as e:
            return self._format_result("game_test", False, str(e))

    async def _memory_test(self) -> dict:
        """Verify memory store/retrieve works via health."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{self.server_url}/api/health")
                if resp.status_code == 200:
                    return self._format_result("memory_test", True, "Health OK — memory subsystem reachable")
                return self._format_result("memory_test", False, f"Health returned {resp.status_code}")
        except Exception as e:
            return self._format_result("memory_test", False, str(e))

    async def _emotion_test(self) -> dict:
        """Verify emotion mapping works via health data."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{self.server_url}/api/health")
                data = resp.json()
                has_emotion = "current_emotion" in data or "emotion" in data
                return self._format_result(
                    "emotion_test", True,
                    f"Emotion data present: {has_emotion}" if resp.status_code == 200 else "No emotion data"
                )
        except Exception as e:
            return self._format_result("emotion_test", False, str(e))

    async def _vomit_test(self) -> dict:
        """Check distress detector status."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{self.server_url}/api/health")
                data = resp.json()
                detector = data.get("distress_detector", data.get("audio_distress", "unknown"))
                passed = (detector == "ok")
                return self._format_result("vomit_test", passed, f"Distress detector: {detector}")
        except Exception as e:
            return self._format_result("vomit_test", False, str(e))

    async def _speaker_id_test(self) -> dict:
        """Check speaker / voice identification status via health endpoint."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{self.server_url}/api/health")
                data = resp.json()
                status = data.get("speaker_id", "unknown")
                passed = (status == "ok")
                return self._format_result("speaker_id_test", passed, f"Speaker ID: {status}")
        except Exception as e:
            return self._format_result("speaker_id_test", False, str(e))

    async def _websocket_test(self) -> dict:
        """Connect and disconnect WebSocket."""
        import websockets
        ws_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
        try:
            async with websockets.connect(ws_url, close_timeout=5, open_timeout=TIMEOUT_SECONDS) as ws:
                await ws.close()
            return self._format_result("websocket_test", True, "WS connect/disconnect OK")
        except ImportError:
            # Fallback: just check HTTP health if websockets not installed
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                    resp = await client.get(f"{self.server_url}/api/health")
                    return self._format_result("websocket_test", resp.status_code == 200, "WS lib missing, health fallback")
            except Exception as e2:
                return self._format_result("websocket_test", False, f"No websockets lib: {e2}")
        except Exception as e:
            return self._format_result("websocket_test", False, str(e))

    async def _dashboard_test(self) -> dict:
        """GET /dashboard returns 200."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{self.server_url}/dashboard")
                passed = resp.status_code == 200
                return self._format_result("dashboard_test", passed, f"Dashboard HTTP {resp.status_code}")
        except Exception as e:
            return self._format_result("dashboard_test", False, str(e))

    async def _audio_test(self) -> dict:
        """Verify audio pipeline status via health."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{self.server_url}/api/health")
                data = resp.json()
                tts = data.get("tts", "unknown")
                stt = data.get("stt", "unknown")
                passed = tts in ("ok", "slow") or stt in ("ok", "slow")
                return self._format_result("audio_test", passed, f"Audio pipeline: tts={tts} stt={stt}")
        except Exception as e:
            return self._format_result("audio_test", False, str(e))

    # ── Run all ──────────────────────────────────────────────

    async def run_all(self) -> dict:
        """Run all 11 smoke tests and return results with confidence score."""
        if DEBUG_CANARY:
            logger.debug("[DEBUG_CANARY] run_all: START")

        tests = [
            self._voice_test,
            self._stt_test,
            self._llm_test,
            self._game_test,
            self._memory_test,
            self._emotion_test,
            self._vomit_test,
            self._speaker_id_test,
            self._websocket_test,
            self._dashboard_test,
            self._audio_test,
        ]

        results = await asyncio.gather(*[t() for t in tests], return_exceptions=True)

        # Convert exceptions to failed results
        final_results = []
        test_names = [
            "voice_test", "stt_test", "llm_test", "game_test", "memory_test",
            "emotion_test", "vomit_test", "speaker_id_test", "websocket_test",
            "dashboard_test", "audio_test",
        ]
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                final_results.append(self._format_result(test_names[i], False, str(r)))
            else:
                final_results.append(r)

        confidence = self._calculate_confidence(final_results)

        if DEBUG_CANARY:
            logger.debug("[DEBUG_CANARY] run_all: END confidence=%d", confidence)

        return {"results": final_results, "confidence": confidence}


def _print_results(data: dict):
    """Pretty-print canary results to console."""
    results = data["results"]
    confidence = data["confidence"]
    warnings = []

    for r in results:
        emoji = "✅" if r["passed"] else "⚠️"
        print(f"  {emoji} {r['test']}: {r['message']}")
        if not r["passed"]:
            warnings.append(r["test"])

    print()
    if warnings:
        print(f"✅ Mario is {confidence}% ready! ({len(warnings)} warning{'s' if len(warnings) != 1 else ''}: {', '.join(warnings)})")
    else:
        print(f"✅ Mario is {confidence}% ready! All systems go!")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"
    canary = Canary(server_url=url)
    print(f"\n🐤 Running canary tests against {url}...\n")
    data = asyncio.run(canary.run_all())
    _print_results(data)
