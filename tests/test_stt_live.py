"""Live STT E2E Test — sends real audio to the running Mario server via WebSocket.

Connects to ws://localhost:8765/ws, sends TTS-generated audio as raw PCM binary
frames (simulating mic input), and monitors for STT transcription in the response.

Usage:
  python tests/test_stt_live.py
"""
import sys
import os
import json
import time
import wave
import io
import asyncio
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

SAMPLE_RATE = 16000
WS_URL = "ws://localhost:8765/ws"


def wav_to_raw_pcm(wav_bytes: bytes) -> bytes:
    """Strip WAV header and return raw PCM int16 bytes, resampled to 16kHz mono."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        params = wf.getparams()
        raw = wf.readframes(params.nframes)

    samples = np.frombuffer(raw, dtype=np.int16)

    # Convert stereo to mono if needed
    if params.nchannels == 2:
        samples = samples.reshape(-1, 2).mean(axis=1).astype(np.int16)

    # Resample if not 16kHz
    if params.framerate != SAMPLE_RATE:
        from scipy.signal import resample
        num_samples = int(len(samples) * SAMPLE_RATE / params.framerate)
        samples = resample(samples, num_samples).astype(np.int16)

    return samples.tobytes()


async def run_test():
    try:
        import websockets
    except ImportError:
        print("Installing websockets...")
        os.system(f'"{sys.executable}" -m pip install websockets --quiet')
        import websockets

    print("="*60)
    print("  Mario AI — Live STT E2E Test")
    print("="*60)

    print("\n[1] Generating test audio via TTS...")
    import tts
    tts.init_tts()

    test_phrases = [
        ("Hello Mario, how are you today?", "greeting"),
        ("Let's play rock paper scissors!", "game command"),
        ("What is your favorite food?", "question"),
    ]

    audio_samples = []
    for phrase, label in test_phrases:
        wav_audio = tts.synthesize(phrase)
        if wav_audio:
            # Convert WAV to raw PCM (what the mic would send)
            raw_pcm = wav_to_raw_pcm(wav_audio)
            duration = len(raw_pcm) / (SAMPLE_RATE * 2)
            print(f"  ✅ Generated: \"{phrase}\" ({duration:.1f}s, {len(raw_pcm)} raw PCM bytes)")
            audio_samples.append((phrase, label, raw_pcm))
        else:
            print(f"  ❌ TTS failed for: \"{phrase}\"")

    if not audio_samples:
        print("\n❌ No audio generated. Aborting.")
        return

    print(f"\n[2] Connecting to {WS_URL}...")

    try:
        async with websockets.connect(WS_URL, max_size=10*1024*1024) as ws:
            print("  ✅ Connected!")

            # Read the initial greeting (drain all startup messages)
            print("\n[3] Waiting for Mario's greeting...")
            greeting = None
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=20)
                    if isinstance(msg, str):
                        data = json.loads(msg)
                        if data.get("type") in ("response", "mario_response"):
                            greeting = data.get("text", "")
                            print(f"  🍄 Mario says: \"{greeting[:80]}...\"" if len(greeting) > 80 else f"  🍄 Mario says: \"{greeting}\"")
                            # Keep draining for a bit to clear audio/pose messages
                            try:
                                while True:
                                    await asyncio.wait_for(ws.recv(), timeout=3)
                            except asyncio.TimeoutError:
                                pass
                            break
            except asyncio.TimeoutError:
                print("  ⚠️  No greeting received (timeout)")

            # Test each phrase
            print(f"\n[4] Sending {len(audio_samples)} test phrases as raw PCM audio...")
            print("-"*60)

            results = []
            for phrase, label, raw_pcm in audio_samples:
                print(f"\n  📤 Sending: \"{phrase}\" ({label})")

                # Send raw PCM as one binary message (server buffers internally)
                await ws.send(raw_pcm)
                chunks_sent = 1

                print(f"     Sent {len(raw_pcm)} bytes = {len(raw_pcm)/(SAMPLE_RATE*2):.1f}s audio")

                # Send tiny follow-up after delay to trigger buffer flush
                await asyncio.sleep(2)
                await ws.send(np.zeros(100, dtype=np.int16).tobytes())

                # Wait for Mario's response
                response_text = None
                try:
                    deadline = time.time() + 45
                    while time.time() < deadline:
                        msg = await asyncio.wait_for(ws.recv(), timeout=10)
                        if isinstance(msg, str):
                            data = json.loads(msg)
                            msg_type = data.get("type", "")
                            if msg_type in ("response", "mario_response"):
                                response_text = data.get("text", "")
                                print(f"  📥 Mario replied: \"{response_text[:100]}\"")
                                # Drain remaining messages for this response
                                try:
                                    while True:
                                        await asyncio.wait_for(ws.recv(), timeout=3)
                                except asyncio.TimeoutError:
                                    pass
                                break
                            elif msg_type == "transcript":
                                print(f"     📝 STT transcript: \"{data.get('text', '')}\"")
                            elif msg_type == "thinking":
                                print(f"     💭 Thinking...")
                except asyncio.TimeoutError:
                    pass

                if response_text:
                    results.append((phrase, True, response_text))
                else:
                    print(f"  ❌ No response received")
                    results.append((phrase, False, None))

                # Cooldown between phrases
                await asyncio.sleep(5)

            # Summary
            print("\n" + "="*60)
            print("  Results")
            print("="*60)
            passed = sum(1 for _, ok, _ in results if ok)
            for phrase, ok, response in results:
                icon = "✅" if ok else "❌"
                resp_preview = f" → \"{response[:60]}\"" if response else " → No response"
                print(f"  {icon} \"{phrase}\"{resp_preview}")

            print(f"\n  {passed}/{len(results)} phrases got responses")

    except ConnectionRefusedError:
        print(f"  ❌ Cannot connect to {WS_URL}")
        print("     Is the Mario server running? Start with: python server/main.py")
    except Exception as e:
        import traceback
        print(f"  ❌ Error: {type(e).__name__}: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_test())
