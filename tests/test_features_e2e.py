"""E2E feature test — sends text to Mario server via WebSocket, captures screenshots."""
import asyncio
import json
import time
import sys
import os
import ctypes
from ctypes import wintypes

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

try:
    import websockets
except ImportError:
    sys.exit("pip install websockets first")

WS_URL = "ws://localhost:8765/ws"

# Screenshot helper
def capture_mario_window(filename: str):
    """Capture Mario AI window regardless of position."""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    hwnd_result = [None]
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    def cb(h, lp):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, buf, 256)
        if 'Mario AI' in buf.value and user32.IsWindowVisible(h):
            hwnd_result[0] = h
            return False
        return True
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    hwnd = hwnd_result[0]
    if not hwnd:
        print(f"  [SKIP] Mario window not found for screenshot")
        return False

    class RECT(ctypes.Structure):
        _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                    ('right', ctypes.c_long), ('bottom', ctypes.c_long)]
    wrect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wrect))
    ww = wrect.right - wrect.left
    wh = wrect.bottom - wrect.top

    hdc = user32.GetDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, ww, wh)
    old = gdi32.SelectObject(memdc, bmp)
    user32.PrintWindow(hwnd, memdc, 2)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
            ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
            ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG), ('biYPelsPerMeter', wintypes.LONG),
            ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD),
        ]
    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = ww
    bmi.biHeight = -wh
    bmi.biPlanes = 1
    bmi.biBitCount = 32

    buf = ctypes.create_string_buffer(ww * wh * 4)
    gdi32.GetDIBits(memdc, bmp, 0, wh, buf, ctypes.byref(bmi), 0)

    from PIL import Image
    img = Image.frombuffer('RGBA', (ww, wh), buf, 'raw', 'BGRA', 0, 1)
    img.save(filename)
    gdi32.SelectObject(memdc, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)
    print(f"  📸 Saved {filename}")
    return True


async def send_text_and_wait(ws, text, wait_for_audio=True, timeout=30):
    """Send text input and collect all responses until mario_response + audio."""
    msg = json.dumps({"type": "text_input", "text": text})
    await ws.send(msg)
    print(f"\n  → Sent: '{text}'")

    responses = []
    audio_received = False
    start = time.time()

    while time.time() - start < timeout:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
        except asyncio.TimeoutError:
            if not wait_for_audio or audio_received:
                break
            continue

        if isinstance(raw, bytes):
            audio_received = True
            print(f"  🔊 Audio received: {len(raw)} bytes")
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        msg_type = data.get("type", "")
        if msg_type in ("mario_response", "response"):
            text_resp = data.get("text", "")
            emotion = data.get("emotion", "")
            pose = data.get("pose_hint", "")
            print(f"  🍄 Mario: {text_resp[:100]}")
            if emotion:
                print(f"     Emotion: {emotion}")
            if pose:
                print(f"     Pose: {pose}")
            responses.append(data)
        elif msg_type == "game_state":
            print(f"  🎮 Game state: {data}")
            responses.append(data)
        elif msg_type == "leaderboard_update":
            pass  # ignore
        elif msg_type not in ("health_pong",):
            print(f"  📨 {msg_type}: {json.dumps(data)[:120]}")
            responses.append(data)

        if responses and (not wait_for_audio or audio_received):
            await asyncio.sleep(1)
            break

    return responses


async def run_tests():
    """Run comprehensive feature tests."""
    print("=" * 60)
    print("MARIO AI FEATURE E2E TEST")
    print("=" * 60)

    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    async with websockets.connect(WS_URL) as ws:
        # Wait for initial connection
        await asyncio.sleep(2)

        # ─── 1. Basic conversation ───
        print("\n" + "=" * 40)
        print("TEST 1: Basic Conversation")
        print("=" * 40)
        r = await send_text_and_wait(ws, "Hello Mario! How are you today?")
        time.sleep(3)
        capture_mario_window(os.path.join(screenshots_dir, "01_greeting.png"))

        # ─── 2. Question (? bubble style) ───
        print("\n" + "=" * 40)
        print("TEST 2: Question Bubble Style")
        print("=" * 40)
        r = await send_text_and_wait(ws, "What is your favorite food?")
        time.sleep(3)
        capture_mario_window(os.path.join(screenshots_dir, "02_question.png"))

        # ─── 3. Start a game — Riddles ───
        print("\n" + "=" * 40)
        print("TEST 3: Game — Riddles")
        print("=" * 40)
        r = await send_text_and_wait(ws, "Let's play riddles!")
        time.sleep(4)
        capture_mario_window(os.path.join(screenshots_dir, "03_riddles_start.png"))

        # Try answering the riddle
        r = await send_text_and_wait(ws, "Is it a mushroom?")
        time.sleep(3)
        capture_mario_window(os.path.join(screenshots_dir, "04_riddles_answer.png"))

        # Quit game
        r = await send_text_and_wait(ws, "quit game")
        time.sleep(2)

        # ─── 4. Game — Rock Paper Scissors ───
        print("\n" + "=" * 40)
        print("TEST 4: Game — Rock Paper Scissors")
        print("=" * 40)
        r = await send_text_and_wait(ws, "Let's play rock paper scissors!")
        time.sleep(4)
        capture_mario_window(os.path.join(screenshots_dir, "05_rps_start.png"))

        r = await send_text_and_wait(ws, "rock")
        time.sleep(3)
        capture_mario_window(os.path.join(screenshots_dir, "06_rps_play.png"))

        r = await send_text_and_wait(ws, "quit game")
        time.sleep(2)

        # ─── 5. Game — Would You Rather ───
        print("\n" + "=" * 40)
        print("TEST 5: Game — Would You Rather")
        print("=" * 40)
        r = await send_text_and_wait(ws, "Let's play would you rather!")
        time.sleep(4)
        capture_mario_window(os.path.join(screenshots_dir, "07_wyr_start.png"))

        r = await send_text_and_wait(ws, "A")
        time.sleep(3)

        r = await send_text_and_wait(ws, "quit game")
        time.sleep(2)

        # ─── 6. Game — Truth or Dare ───
        print("\n" + "=" * 40)
        print("TEST 6: Game — Truth or Dare")
        print("=" * 40)
        r = await send_text_and_wait(ws, "Let's play truth or dare!")
        time.sleep(4)
        capture_mario_window(os.path.join(screenshots_dir, "08_tod_start.png"))

        r = await send_text_and_wait(ws, "truth")
        time.sleep(3)
        capture_mario_window(os.path.join(screenshots_dir, "09_tod_truth.png"))

        r = await send_text_and_wait(ws, "quit game")
        time.sleep(2)

        # ─── 7. Game — Word Chain ───
        print("\n" + "=" * 40)
        print("TEST 7: Game — Word Chain")
        print("=" * 40)
        r = await send_text_and_wait(ws, "Let's play word chain!")
        time.sleep(4)
        capture_mario_window(os.path.join(screenshots_dir, "10_wordchain_start.png"))

        r = await send_text_and_wait(ws, "elephant")
        time.sleep(3)

        r = await send_text_and_wait(ws, "quit game")
        time.sleep(2)

        # ─── 8. Game — Simon Says ───
        print("\n" + "=" * 40)
        print("TEST 8: Game — Simon Says")
        print("=" * 40)
        r = await send_text_and_wait(ws, "Let's play simon says!")
        time.sleep(4)
        capture_mario_window(os.path.join(screenshots_dir, "11_simon_start.png"))

        r = await send_text_and_wait(ws, "yes")
        time.sleep(3)

        r = await send_text_and_wait(ws, "quit game")
        time.sleep(2)

        # ─── 9. Game — Rapid Fire ───
        print("\n" + "=" * 40)
        print("TEST 9: Game — Rapid Fire Quiz")
        print("=" * 40)
        r = await send_text_and_wait(ws, "Let's play rapid fire!")
        time.sleep(4)
        capture_mario_window(os.path.join(screenshots_dir, "12_rapidfire_start.png"))

        r = await send_text_and_wait(ws, "mushroom")
        time.sleep(3)

        r = await send_text_and_wait(ws, "quit game")
        time.sleep(2)

        # ─── 10. Emotional responses ───
        print("\n" + "=" * 40)
        print("TEST 10: Emotional Responses")
        print("=" * 40)

        r = await send_text_and_wait(ws, "Tell me a really funny joke!")
        time.sleep(4)
        capture_mario_window(os.path.join(screenshots_dir, "13_funny.png"))

        r = await send_text_and_wait(ws, "I'm feeling really sad today...")
        time.sleep(4)
        capture_mario_window(os.path.join(screenshots_dir, "14_sad.png"))

        r = await send_text_and_wait(ws, "BOWSER IS ATTACKING THE CASTLE RIGHT NOW!")
        time.sleep(4)
        capture_mario_window(os.path.join(screenshots_dir, "15_shout.png"))

        # ─── 11. Bathroom/setting awareness ───
        print("\n" + "=" * 40)
        print("TEST 11: Setting Awareness")
        print("=" * 40)
        r = await send_text_and_wait(ws, "What do you think about this bathroom?")
        time.sleep(4)
        capture_mario_window(os.path.join(screenshots_dir, "16_bathroom.png"))

        # ─── 12. Long text (pagination test) ───
        print("\n" + "=" * 40)
        print("TEST 12: Long Response Pagination")
        print("=" * 40)
        r = await send_text_and_wait(ws, "Tell me a very long story about your adventures in the Mushroom Kingdom!")
        time.sleep(6)
        capture_mario_window(os.path.join(screenshots_dir, "17_long_text.png"))

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print(f"Screenshots saved to: {screenshots_dir}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
