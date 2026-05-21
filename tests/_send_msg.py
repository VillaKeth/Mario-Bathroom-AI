"""Send a test message and wait for response."""
import asyncio
import json
import time
import websockets

async def test():
    async with websockets.connect("ws://localhost:8765/ws", ping_interval=None) as ws:
        # Wait for greeting
        start = time.time()
        while time.time() - start < 15:
            try:
                data = await asyncio.wait_for(ws.recv(), timeout=5)
                if isinstance(data, str):
                    parsed = json.loads(data)
                    if parsed.get("type") == "mario_response":
                        print(f"GREETING: {parsed['text'][:100]}")
                        break
            except asyncio.TimeoutError:
                pass
        
        await asyncio.sleep(3)
        
        # Send exciting message
        await ws.send(json.dumps({"type": "text_input", "text": "Tell me a joke about mushrooms!"}))
        
        # Wait for response
        start = time.time()
        while time.time() - start < 30:
            try:
                data = await asyncio.wait_for(ws.recv(), timeout=5)
                if isinstance(data, str):
                    parsed = json.loads(data)
                    if parsed.get("type") == "mario_response":
                        print(f"RESPONSE: {parsed['text'][:200]}")
                        print(f"EMOTION: {parsed.get('emotion')}")
                        print(f"POSE: {parsed.get('pose_hint')}")
                        break
                    elif parsed.get("type") == "state":
                        print(f"STATE: thinking={parsed.get('thinking')}")
            except asyncio.TimeoutError:
                pass
        
        await asyncio.sleep(5)
        print("DONE - screenshot now")

asyncio.run(test())
