"""Quick WebSocket conversation test — measures end-to-end latency."""
import asyncio, websockets, json, time

async def test_chat():
    uri = "ws://localhost:8765/ws"
    async with websockets.connect(uri) as ws:
        msg = json.dumps({
            "type": "text_input",
            "text": "Hey Mario, tell me a joke!",
            "speaker_name": "TestUser"
        })
        t0 = time.time()
        await ws.send(msg)

        responses = []
        audio_chars = 0
        first_audio_time = None
        while True:
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=30)
                elapsed = time.time() - t0
                # Binary frame = audio data
                if isinstance(resp, bytes):
                    if first_audio_time is None:
                        first_audio_time = elapsed
                    audio_chars += len(resp)
                    print(f"  [{elapsed:.1f}s] AUDIO CHUNK: {len(resp)} bytes")
                    continue
                data = json.loads(resp)
                msg_type = data.get("type", "unknown")

                if msg_type == "mario_response":
                    text = data.get("text", "")[:120]
                    aud_len = len(data.get("audio_base64", ""))
                    if aud_len > 0 and first_audio_time is None:
                        first_audio_time = elapsed
                    print(f"  [{elapsed:.1f}s] RESPONSE: {text}")
                    print(f"           audio={aud_len} chars, emotion={data.get('emotion')}")
                    responses.append(data)
                    audio_chars += aud_len
                elif msg_type == "mario_thinking":
                    print(f"  [{elapsed:.1f}s] THINKING...")
                elif msg_type == "state_change":
                    print(f"  [{elapsed:.1f}s] STATE -> {data.get('state')}")
                else:
                    print(f"  [{elapsed:.1f}s] {msg_type}")
            except asyncio.TimeoutError:
                break

        total = time.time() - t0
        print(f"\n--- Results ---")
        print(f"Total time: {total:.1f}s")
        print(f"First audio at: {first_audio_time:.1f}s" if first_audio_time else "No audio received")
        print(f"Responses: {len(responses)}")
        print(f"Audio data: ~{audio_chars // 1000}KB")

asyncio.run(test_chat())
