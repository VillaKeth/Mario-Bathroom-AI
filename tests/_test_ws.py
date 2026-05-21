"""Send a test message via WebSocket to trigger Mario's speech bubble."""
import asyncio, websockets, json

async def test():
    async with websockets.connect("ws://localhost:8765/ws") as ws:
        msg = json.dumps({
            "type": "chat",
            "message": "Tell me the longest story you can about every single adventure you have ever been on. List every world, every enemy, every power-up. Give me the full detailed story please!",
            "guest_name": "TestUser"
        })
        await ws.send(msg)
        for i in range(5):
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=15)
                if isinstance(resp, str):
                    data = json.loads(resp)
                    if data.get("type") == "mario_response":
                        print("MARIO TEXT:", data.get("text", "")[:500])
                        break
                    else:
                        print("Got type:", data.get("type"))
            except asyncio.TimeoutError:
                print("Timeout", i)

asyncio.run(test())
