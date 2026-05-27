"""Test that game triggers route correctly from text_input."""
import asyncio
import websockets
import json
import time
import pytest

@pytest.mark.asyncio
async def test_games():
    uri = "ws://localhost:8765/ws"
    async with websockets.connect(uri) as ws:
        await asyncio.sleep(2)
        # Drain initial messages
        while True:
            try:
                await asyncio.wait_for(ws.recv(), timeout=0.5)
            except Exception:
                break

        tests = [
            ("Let's play riddles!", "riddles"),
            ("Let's play rock paper scissors!", "rps"),
            ("Let's play simon says!", "simon"),
            ("Let's play word chain!", "word_chain"),
            ("Let's play would you rather!", "wyr"),
            ("Let's play rapid fire!", "rapid_fire"),
        ]

        results = {}
        for text, label in tests:
            print(f"\n{'='*50}")
            print(f"TEST: {label}")
            print(f"{'='*50}")
            print(f"  Sending: {text}")
            await ws.send(json.dumps({"type": "text_input", "text": text}))

            # Collect responses for 8s
            responses = []
            start = time.time()
            while time.time() - start < 8:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    if isinstance(msg, str):
                        data = json.loads(msg)
                        if data.get("type") == "mario_response":
                            resp_text = data["text"][:150]
                            responses.append(resp_text)
                            print(f"  Mario: {resp_text}")
                except Exception:
                    pass

            if not responses:
                print("  NO RESPONSE!")
                results[label] = "NO RESPONSE"
            else:
                results[label] = responses[0]

            # Quit game + wait
            await ws.send(json.dumps({"type": "text_input", "text": "quit game"}))
            await asyncio.sleep(5)
            while True:
                try:
                    await asyncio.wait_for(ws.recv(), timeout=0.5)
                except Exception:
                    break

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        for label, resp in results.items():
            # Check if response looks like a game start
            game_keywords = {
                "riddles": ["riddle", "puzzle", "guess", "answer"],
                "rps": ["rock", "paper", "scissors", "choose", "throw"],
                "simon": ["simon", "says", "follow", "do this"],
                "word_chain": ["word", "chain", "letter", "start"],
                "wyr": ["rather", "would you", "option", "choice"],
                "rapid_fire": ["rapid", "fire", "quick", "fast", "round", "question"],
            }
            keywords = game_keywords.get(label, [])
            is_game = any(kw in resp.lower() for kw in keywords)
            status = "GAME STARTED" if is_game else "MISSED"
            print(f"  {label}: {status}")
            print(f"    Response: {resp[:100]}")

asyncio.run(test_games())
