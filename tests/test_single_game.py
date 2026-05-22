"""Send a single game request and wait for a long time to see timing."""
import asyncio
import websockets
import json
import time

async def test():
    uri = "ws://localhost:8765/ws"
    async with websockets.connect(uri) as ws:
        # Wait for connection
        await asyncio.sleep(3)
        # Drain
        while True:
            try:
                await asyncio.wait_for(ws.recv(), timeout=1.0)
            except Exception:
                break

        text = "Let's play riddles!"
        print(f"[{time.strftime('%H:%M:%S')}] Sending: {text}")
        await ws.send(json.dumps({"type": "text_input", "text": text}))

        start = time.time()
        while time.time() - start < 30:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                elapsed = time.time() - start
                if isinstance(msg, str):
                    data = json.loads(msg)
                    mtype = data.get("type", "?")
                    if mtype == "mario_response":
                        txt = data.get("text", "")[:120]
                        print(f"  [{elapsed:.1f}s] RESPONSE: {txt}")
                        print(f"           emotion={data.get('emotion')} has_audio={data.get('has_audio')}")
                    elif mtype == "state":
                        print(f"  [{elapsed:.1f}s] STATE: {json.dumps({k:v for k,v in data.items() if k != 'type'})[:100]}")
                    elif mtype == "audio_chunk":
                        print(f"  [{elapsed:.1f}s] AUDIO_CHUNK: idx={data.get('chunk_index')} total={data.get('total_chunks')} last={data.get('is_last')}")
                    elif mtype == "heartbeat":
                        pass  # skip heartbeats
                    else:
                        print(f"  [{elapsed:.1f}s] {mtype}: {str(data)[:80]}")
                elif isinstance(msg, bytes):
                    elapsed = time.time() - start
                    print(f"  [{elapsed:.1f}s] AUDIO_BYTES: {len(msg)} bytes")
            except asyncio.TimeoutError:
                pass
        
        print(f"\nDone after 30s")

asyncio.run(test())
