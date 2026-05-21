"""Quick visual test — send message, wait for response, capture screenshot."""
import asyncio
import json
import time
import sys
import ctypes
import ctypes.wintypes
import os

try:
    import websockets
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets", "-q"])
    import websockets

from PIL import ImageGrab, Image

# Fix DPI awareness for screen capture
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

SERVER = "ws://localhost:8765/ws"
OUT_DIR = "C:/Users/Vketh/Desktop/Mario_AI"

def capture_mario():
    """Capture full screen (most reliable on Windows)."""
    try:
        img = ImageGrab.grab()
        return img
    except Exception as e:
        print(f"ERROR: Screen grab failed: {e}")
        return None

async def test_visual():
    print("=== Visual Test ===")
    
    # Phase 1: Capture idle state
    print("\n[1] Capturing idle state...")
    idle_img = capture_mario()
    if idle_img:
        idle_img.save(f"{OUT_DIR}/_test_idle.png")
        print(f"   Saved idle screenshot: {idle_img.size}")
    
    # Phase 2: Send a message and capture response
    print("\n[2] Sending message 'Tell me about pasta!'...")
    async with websockets.connect(SERVER, ping_interval=None) as ws:
        msg = json.dumps({"type": "text_input", "text": "Tell me about your favorite pasta dish!", "speaker_id": "TestUser"})
        await ws.send(msg)
        
        got_response = False
        got_audio = False
        response_text = ""
        emotion = ""
        
        start = time.time()
        while time.time() - start < 45:
            try:
                data = await asyncio.wait_for(ws.recv(), timeout=5.0)
                if isinstance(data, str):
                    parsed = json.loads(data)
                    if parsed.get("type") == "mario_response":
                        got_response = True
                        response_text = parsed.get("text", "")
                        emotion = parsed.get("emotion", "unknown")
                        print(f"   Response: {response_text[:120]}")
                        print(f"   Emotion: {emotion}")
                        print(f"   Energy: {parsed.get('energy', 'N/A')}")
                        print(f"   Pose: {parsed.get('pose_hint', 'N/A')}")
                        print(f"   Animation: {parsed.get('animation', 'N/A')}")
                        # Wait a moment for the display to update
                        await asyncio.sleep(2)
                        response_img = capture_mario()
                        if response_img:
                            response_img.save(f"{OUT_DIR}/_test_response.png")
                            print(f"   Saved response screenshot: {response_img.size}")
                elif isinstance(data, bytes):
                    got_audio = True
                    print(f"   Audio: {len(data)} bytes")
                    if got_response:
                        # Wait for audio to play before capturing
                        await asyncio.sleep(3)
                        playing_img = capture_mario()
                        if playing_img:
                            playing_img.save(f"{OUT_DIR}/_test_playing.png")
                            print(f"   Saved playing screenshot: {playing_img.size}")
                        break
            except asyncio.TimeoutError:
                if got_response:
                    break
        
        if not got_response:
            print("   ERROR: No response received!")
    
    # Phase 3: Trigger a shot event 
    print("\n[3] Triggering 'mario_kart' event...")
    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post("http://localhost:8765/admin/trigger_event/mario_kart")
        print(f"   Trigger response: {r.status_code} - {r.text[:100]}")
        
        # Wait for event to start displaying
        await asyncio.sleep(5)
        event_img = capture_mario()
        if event_img:
            event_img.save(f"{OUT_DIR}/_test_event.png")
            print(f"   Saved event screenshot: {event_img.size}")
        
        # Wait for countdown phase
        await asyncio.sleep(10)
        countdown_img = capture_mario()
        if countdown_img:
            countdown_img.save(f"{OUT_DIR}/_test_countdown.png")
            print(f"   Saved countdown screenshot: {countdown_img.size}")
    
    print("\n=== Visual Test Complete ===")
    print("Screenshots saved as _test_*.png")

if __name__ == "__main__":
    asyncio.run(test_visual())
