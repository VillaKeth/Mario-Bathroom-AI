import ctypes, ctypes.wintypes, struct
from ctypes import create_string_buffer
from PIL import Image

hwnd = 2820212
rect = ctypes.wintypes.RECT()
ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
w, h = rect.right, rect.bottom
print(f"Window size: {w}x{h}")

hdc_screen = ctypes.windll.user32.GetDC(hwnd)
hdc_mem = ctypes.windll.gdi32.CreateCompatibleDC(hdc_screen)
hbm = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
ctypes.windll.gdi32.SelectObject(hdc_mem, hbm)
ctypes.windll.user32.PrintWindow(hwnd, hdc_mem, 2)

bmi = create_string_buffer(40)
struct.pack_into('IiiHHIIiiII', bmi, 0, 40, w, -h, 1, 32, 0, w*h*4, 0, 0, 0, 0)
bits = create_string_buffer(w * h * 4)
ctypes.windll.gdi32.GetDIBits(hdc_mem, hbm, 0, h, bits, bmi, 0)

img = Image.frombuffer('RGBA', (w, h), bits, 'raw', 'BGRA', 0, 1)
img.save(r'C:\Users\Vketh\Desktop\Mario_AI\pygame_screenshot.png')
print("Screenshot saved")

ctypes.windll.gdi32.DeleteObject(hbm)
ctypes.windll.gdi32.DeleteDC(hdc_mem)
ctypes.windll.user32.ReleaseDC(hwnd, hdc_screen)
