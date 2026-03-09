"""Integration test for Mario AI server — tests text_input pipeline end-to-end."""
import asyncio
import websockets
import json
import time
import urllib.request

async def test():
    print("=== Mario Integration Test ===")
    print()

    # 1. Check health
    try:
        resp = urllib.request.urlopen("http://localhost:8765/health", timeout=5)
        health = json.loads(resp.read())
        print(f"Health: status={health['status']}, cache={health['tts_cache_size']}, "
              f"precache_done={health.get('precache_done')}, precache_active={health.get('precache_active')}")
    except Exception as e:
        print(f"Health check failed: {e}")
        return

    # 2. Connect via WebSocket
    uri = "ws://localhost:8765/ws"
    async with websockets.connect(uri, max_size=10*1024*1024) as ws:
        print("Connected to WebSocket")

        # Drain initial messages
        for _ in range(5):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                if isinstance(msg, str):
                    d = json.loads(msg)
                    print(f"  Init: type={d.get('type')}, text={str(d.get('text',''))[:60]}")
            except asyncio.TimeoutError:
                break

        # Test cases
        tests = [
            ("hello", "Hey Mario, how are you?"),
            ("joke", "Tell me a quick joke"),
            ("bye", "Goodbye Mario!"),
        ]

        results = []
        for name, text in tests:
            print(f"\n--- Test: {name} ---")
            print(f"Sending: {text}")
            t0 = time.time()

            await ws.send(json.dumps({"type": "text_input", "text": text}))

            got_text = False
            audio_frames = 0
            response_text = ""

            deadline = time.time() + 60.0
            while time.time() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    if isinstance(msg, bytes):
                        audio_frames += 1
                        print(f"  AUDIO: {len(msg)} bytes")
                    else:
                        d = json.loads(msg)
                        mtype = d.get("type")
                        if mtype == "mario_response":
                            response_text = d.get("text", "")
                            got_text = True
                            resp_time = d.get("response_time", 0)
                            print(f"  TEXT: {response_text[:80]}")
                            print(f"  Server response_time: {resp_time}s")
                            if not d.get("has_audio"):
                                break
                        elif mtype == "state":
                            pass
                        else:
                            print(f"  OTHER: type={mtype}")
                    if got_text and audio_frames > 0:
                        break
                except asyncio.TimeoutError:
                    if got_text:
                        break
                    print("  (waiting...)")
                    continue

            elapsed = time.time() - t0
            passed = got_text and audio_frames > 0
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {name}: text={got_text}, audio={audio_frames}, time={elapsed:.1f}s")
            results.append((name, passed, elapsed))

            # Respect 2s text_input cooldown
            await asyncio.sleep(3.0)

        print(f"\n=== Results ===")
        passed_count = sum(1 for _, p, _ in results if p)
        total = len(results)
        for name, p, t in results:
            print(f"  {'PASS' if p else 'FAIL'}: {name} ({t:.1f}s)")
        print(f"\n{passed_count}/{total} tests passed")

asyncio.run(test())
