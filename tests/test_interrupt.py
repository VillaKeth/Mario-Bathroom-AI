"""Quick focused test for self-interruption mechanism."""
import asyncio
import json
import time
import websockets

async def test_interruption():
    ws = await websockets.connect("ws://localhost:8765/ws", max_size=10_000_000)
    print("Connected. Draining startup...")
    
    # Drain startup greeting
    while True:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
            if isinstance(msg, str):
                data = json.loads(msg)
                if data.get("type") == "mario_response":
                    print(f"  Startup: {data.get('text', '')[:60]}")
        except asyncio.TimeoutError:
            break
    
    print()
    print("=== TEST: Self-Interruption ===")
    print("Sending long story request...")
    await ws.send(json.dumps({"type": "text_input", "text": "Tell me a really long story about everything you did in the Mushroom Kingdom today"}))
    
    # Wait for thinking or first response
    start = time.time()
    got_response = False
    while time.time() - start < 20:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
            if isinstance(msg, str):
                data = json.loads(msg)
                evt = data.get("type", "")
                if evt == "thinking":
                    print(f"  [{time.time()-start:.1f}s] Mario is thinking...")
                elif evt == "mario_response":
                    print(f"  [{time.time()-start:.1f}s] Story response: {data.get('text', '')[:80]}")
                    got_response = True
                    break
        except asyncio.TimeoutError:
            continue
    
    if not got_response:
        print("  No story response yet, sending interrupt anyway...")
    
    # Wait 1s then send urgent sick message
    await asyncio.sleep(1.0)
    print()
    print(">>> INTERRUPTING: Sending urgent sick message!")
    interrupt_time = time.time()
    await ws.send(json.dumps({"type": "text_input", "text": "Oh no I feel sick I think I am going to throw up"}))
    
    # Collect responses and measure time to sick response
    responses = []
    while time.time() - interrupt_time < 25:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
            if isinstance(msg, str):
                data = json.loads(msg)
                evt = data.get("type", "")
                if evt == "clear_audio":
                    elapsed = time.time() - interrupt_time
                    print(f"  [{elapsed:.1f}s] >>> CLEAR_AUDIO received (interruption working!)")
                elif evt == "thinking":
                    elapsed = time.time() - interrupt_time
                    print(f"  [{elapsed:.1f}s] Thinking (processing sick msg)...")
                elif evt == "mario_response":
                    elapsed = time.time() - interrupt_time
                    text = data.get("text", "")
                    emotion = data.get("emotion", "")
                    print(f"  [{elapsed:.1f}s] Response ({emotion}): {text[:120]}")
                    responses.append((elapsed, text, emotion))
                    
                    # Check if this is the sick response
                    sick_words = ["sick", "throw", "vomit", "okay", "help", "worry", "mama", "water", "rest", "bucket", "here", "cold"]
                    if any(w in text.lower() for w in sick_words):
                        print(f"  >>> SICK RESPONSE arrived in {elapsed:.1f}s!")
                        break
        except asyncio.TimeoutError:
            continue
    
    print()
    print("=== RESULTS ===")
    if responses:
        first_time = responses[0][0]
        print(f"First response: {first_time:.1f}s after interrupt")
        if first_time < 5:
            print("PASS: Fast interruption!")
        else:
            print(f"WARN: Slow ({first_time:.1f}s)")
    else:
        print("FAIL: No response to urgent input")
    
    await ws.close()

asyncio.run(test_interruption())
