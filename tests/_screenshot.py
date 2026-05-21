"""Take a screenshot of the Mario AI pygame window."""
import ctypes
from ctypes import wintypes
import sys

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# Find the pygame window
hwnd = user32.FindWindowW(None, "Mario AI \U0001f344")
if not hwnd:
    print("Window not found")
    sys.exit(1)

# Get window rect
rect = wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
w = rect.right - rect.left
h = rect.bottom - rect.top
print(f"Window: {w}x{h} at ({rect.left},{rect.top})")

# Take screenshot using PrintWindow
hdcSrc = user32.GetDC(hwnd)
hdcDest = gdi32.CreateCompatibleDC(hdcSrc)
hBmp = gdi32.CreateCompatibleBitmap(hdcSrc, w, h)
gdi32.SelectObject(hdcDest, hBmp)
user32.PrintWindow(hwnd, hdcDest, 2)

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]

bmi = BITMAPINFOHEADER()
bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
bmi.biWidth = w
bmi.biHeight = -h
bmi.biPlanes = 1
bmi.biBitCount = 32
bmi.biCompression = 0

buf = ctypes.create_string_buffer(w * h * 4)
gdi32.GetDIBits(hdcDest, hBmp, 0, h, buf, ctypes.byref(bmi), 0)

from PIL import Image
img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
img.save("_screenshot.png")
print(f"Screenshot saved: {w}x{h}")

gdi32.DeleteObject(hBmp)
gdi32.DeleteDC(hdcDest)
user32.ReleaseDC(hwnd, hdcSrc)
