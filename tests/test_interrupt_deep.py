"""Test interruption during LLM generation (not just after response)."""
import asyncio
import json
import time
import websockets

async def test():
    ws = await websockets.connect("ws://localhost:8765/ws", max_size=10_000_000)
    # Drain startup
    while True:
        try:
            await asyncio.wait_for(ws.recv(), timeout=8.0)
        except asyncio.TimeoutError:
            break
    
    print("=== TEST A: Interrupt during THINKING ===")
    await ws.send(json.dumps({"type": "text_input", "text": "Write me a very detailed 500-word essay about mushroom biology"}))
    print("[0.0s] Sent: complex essay request")
    
    start = time.time()
    # Wait ONLY for thinking state, then interrupt immediately
    got_thinking = False
    while time.time() - start < 5:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
            if isinstance(msg, str):
                data = json.loads(msg)
                if data.get("type") == "state" and data.get("thinking"):
                    got_thinking = True
                    print(f"  [{time.time()-start:.1f}s] THINKING state received")
                    break
                elif data.get("type") == "mario_response":
                    print(f"  [{time.time()-start:.1f}s] Response arrived before we could interrupt!")
                    break
        except asyncio.TimeoutError:
            continue
    
    if got_thinking:
        # Interrupt while LLM is still generating!
        await asyncio.sleep(0.1)  # Tiny delay to ensure task is deep in LLM
        t0 = time.time()
        await ws.send(json.dumps({"type": "text_input", "text": "I need to throw up NOW please help"}))
        print(f"  [{time.time()-start:.1f}s] INTERRUPT sent while still thinking!")
        
        got_clear = False
        got_sick = False
        while time.time() - t0 < 20:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                if isinstance(msg, str):
                    data = json.loads(msg)
                    evt = data.get("type", "")
                    elapsed = time.time() - t0
                    if evt == "clear_audio":
                        got_clear = True
                        print(f"  [{elapsed:.1f}s] CLEAR_AUDIO!")
                    elif evt == "mario_response":
                        text = data.get("text", "")
                        emotion = data.get("emotion", "")
                        print(f"  [{elapsed:.1f}s] ({emotion}): {text[:120]}")
                        sick_words = ["sick", "throw", "vomit", "okay", "help", "worry", "here", "water", "rest", "mama", "bucket"]
                        if any(w in text.lower() for w in sick_words):
                            got_sick = True
                            print(f"  >>> SICK RESPONSE in {elapsed:.1f}s!")
                            break
                    elif evt == "state" and data.get("thinking"):
                        print(f"  [{elapsed:.1f}s] Thinking (sick msg)...")
            except asyncio.TimeoutError:
                continue
        
        print(f"\n  clear_audio: {'YES' if got_clear else 'NO'}")
        print(f"  sick_response: {'YES' if got_sick else 'NO'}")
        if got_sick:
            print("  TEST A: PASS!")
        else:
            print("  TEST A: FAIL")
    
    # Wait for cooldown
    await asyncio.sleep(3)
    
    print("\n=== TEST B: Rapid triple-fire (only last should respond) ===")
    t0 = time.time()
    await ws.send(json.dumps({"type": "text_input", "text": "Tell me a joke"}))
    print(f"[0.0s] Sent: joke")
    await asyncio.sleep(0.3)
    await ws.send(json.dumps({"type": "text_input", "text": "Actually sing me a song"}))
    print(f"[0.3s] Sent: song")
    await asyncio.sleep(0.3)
    await ws.send(json.dumps({"type": "text_input", "text": "I feel really sick help me"}))
    print(f"[0.6s] Sent: sick (final)")
    
    # Should get clear_audio twice and then the sick response
    clear_count = 0
    responses = []
    while time.time() - t0 < 20:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
            if isinstance(msg, str):
                data = json.loads(msg)
                evt = data.get("type", "")
                elapsed = time.time() - t0
                if evt == "clear_audio":
                    clear_count += 1
                    print(f"  [{elapsed:.1f}s] CLEAR_AUDIO #{clear_count}")
                elif evt == "mario_response":
                    text = data.get("text", "")
                    emotion = data.get("emotion", "")
                    print(f"  [{elapsed:.1f}s] ({emotion}): {text[:100]}")
                    responses.append(text)
                    if len(responses) >= 1:
                        break
        except asyncio.TimeoutError:
            continue
    
    print(f"\n  clear_audio count: {clear_count}")
    print(f"  responses: {len(responses)}")
    if responses:
        last = responses[-1].lower()
        sick_words = ["sick", "throw", "vomit", "okay", "help", "worry", "here", "water", "rest"]
        if any(w in last for w in sick_words):
            print("  TEST B: PASS (only sick response came through)")
        else:
            print(f"  TEST B: Response was: {last[:80]}")
    
    await ws.close()

asyncio.run(test())
