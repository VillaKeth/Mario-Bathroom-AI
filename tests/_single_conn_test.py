"""Single-connection comprehensive test — mirrors real usage."""
import asyncio
import json
import time
import sys

try:
    import websockets
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets", "-q"])
    import websockets

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "-q"])
    import httpx

SERVER = "ws://localhost:8765/ws"
results = {"pass": 0, "fail": 0, "errors": []}

def log(test, passed, detail=""):
    status = "✅" if passed else "❌"
    results["pass" if passed else "fail"] += 1
    if not passed:
        results["errors"].append(f"{test}: {detail}")
    print(f"  {status} {test}" + (f" — {detail}" if detail else ""))

async def recv_response(ws, timeout=45, skip_greeting=False):
    """Wait for a mario_response, optionally skipping the first one (greeting)."""
    responses = []
    audio_chunks = []
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            data = await asyncio.wait_for(ws.recv(), timeout=8.0)
            if isinstance(data, str):
                parsed = json.loads(data)
                msg_type = parsed.get("type", "")
                if msg_type == "mario_response":
                    responses.append(parsed)
                    if skip_greeting and len(responses) == 1:
                        continue  # Skip first (greeting)
                    return parsed, audio_chunks
                elif msg_type == "thinking":
                    pass  # Expected
            elif isinstance(data, bytes):
                audio_chunks.append(data)
                # If we already have a text response, audio means we're done
                if responses:
                    return responses[-1], audio_chunks
        except asyncio.TimeoutError:
            if responses:
                return responses[-1], audio_chunks
    
    return None, audio_chunks

async def main():
    print("╔══════════════════════════════════════════════╗")
    print("║   Mario AI Single-Connection Test Suite      ║")
    print("╚══════════════════════════════════════════════╝")
    
    # Health check
    async with httpx.AsyncClient() as client:
        r = await client.get("http://localhost:8765/health")
        h = r.json()
        log("Server healthy", h.get("status") == "ok")
    
    async with websockets.connect(SERVER, ping_interval=None) as ws:
        # 1. Wait for greeting
        print("\n═══ Phase 1: Greeting ═══")
        greeting, audio = await recv_response(ws, timeout=30)
        if greeting:
            print(f"  Mario: {greeting['text'][:80]}...")
            log("Greeting received", True)
            log("Greeting has text", bool(greeting.get("text")))
            log("Greeting has emotion", bool(greeting.get("emotion")))
            log("Greeting audio", len(audio) > 0, f"{sum(len(a) for a in audio)} bytes" if audio else "no audio")
            print(f"  Emotion: {greeting.get('emotion')}, Energy: {greeting.get('energy')}")
        else:
            log("Greeting received", False, "No greeting in 30s")
        
        await asyncio.sleep(3)  # Let things settle
        
        # 2. Send conversation messages
        print("\n═══ Phase 2: Conversation ═══")
        test_messages = [
            ("What's your favorite pasta dish?", "Should answer about pasta"),
            ("Tell me a joke!", "Should tell a joke"),
            ("You're amazing Mario!", "Should respond positively"),
            ("I'm feeling sad today", "Should show empathy"),
            ("What games do you like to play?", "Should talk about games"),
        ]
        
        emotions_seen = set()
        for msg_text, expected in test_messages:
            print(f"\n  >>> {msg_text}")
            await ws.send(json.dumps({"type": "text_input", "text": msg_text}))
            resp, audio = await recv_response(ws, timeout=45)
            
            if resp:
                text = resp.get("text", "")
                emotion = resp.get("emotion", "?")
                energy = resp.get("energy", "?")
                pose = resp.get("pose_hint", "?")
                emotions_seen.add(emotion)
                
                print(f"  <<< {text[:100]}...")
                print(f"      emotion={emotion} energy={energy} pose={pose}")
                log(f"Response to '{msg_text[:30]}'", bool(text))
                
                # Check audio
                if audio:
                    total_audio = sum(len(a) for a in audio)
                    log(f"Audio for '{msg_text[:30]}'", total_audio > 1000, f"{total_audio} bytes")
                else:
                    log(f"Audio for '{msg_text[:30]}'", False, "No audio")
            else:
                log(f"Response to '{msg_text[:30]}'", False, "No response in 45s")
            
            await asyncio.sleep(2)  # Rate limit cooldown
        
        log("Multiple emotions produced", len(emotions_seen) >= 2,
            f"Saw {len(emotions_seen)}: {emotions_seen}")
        
        # 3. Test error resilience
        print("\n═══ Phase 3: Error Resilience ═══")
        await ws.send("garbage not json")
        await asyncio.sleep(1)
        await ws.send(json.dumps({"type": "text_input", "text": ""}))
        await asyncio.sleep(1)
        await ws.send(json.dumps({"type": "text_input", "text": "Are you still working?"}))
        resp, _ = await recv_response(ws, timeout=30)
        log("Survives bad input", resp is not None and bool(resp.get("text")))
        
        # 4. Admin commands via text
        print("\n═══ Phase 4: Admin Commands ═══")
        await ws.send(json.dumps({"type": "text_input", "text": "/health"}))
        resp, _ = await recv_response(ws, timeout=15)
        if resp:
            log("Health command", "ok" in resp.get("text", "").lower() or "status" in resp.get("text", "").lower(),
                resp.get("text", "")[:80])
        else:
            log("Health command", False, "No response")
    
    # 5. Event system (separate connection)
    print("\n═══ Phase 5: Event System ═══")
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get("http://localhost:8765/admin/events")
        data = r.json()
        event_count = len(data.get("events", []))
        log("Events loaded", event_count > 100, f"{event_count} events")
    
    # Summary
    print(f"\n{'═' * 50}")
    print(f"  RESULTS: {results['pass']} passed, {results['fail']} failed")
    if results['errors']:
        print(f"\n  FAILURES:")
        for err in results['errors']:
            print(f"    ❌ {err}")
    print(f"{'═' * 50}")
    
    return results['fail'] == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
