import ctypes
import ctypes.wintypes
import time
import pyautogui

# Enable DPI awareness so coordinates match actual pixels
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

found_hwnd = None

def enum_cb(hwnd, lparam):
    global found_hwnd
    length = user32.GetWindowTextLengthW(hwnd)
    if length > 0:
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value
        if 'Mario AI' in title and 'Visual Studio' not in title and 'copilot' not in title.lower():
            found_hwnd = hwnd
            print(f'Found: {title} hwnd={hwnd}')
    return True

user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

if found_hwnd:
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_SHOWWINDOW = 0x0040

    user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
    # Force topmost so terminal can't cover it
    user32.SetWindowPos(found_hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    time.sleep(0.3)

    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(found_hwnd, ctypes.byref(rect))
    x, y, x2, y2 = rect.left, rect.top, rect.right, rect.bottom
    w, h = x2 - x, y2 - y
    print(f'Window rect: ({x}, {y}) {w}x{h}')

    time.sleep(0.3)
    img = pyautogui.screenshot(region=(x, y, w, h))
    # Support custom output filename via sys.argv
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else 'screenshot_mario_front.png'
    img.save(out)
    print(f'Screenshot saved to {out}')

    # Remove topmost
    user32.SetWindowPos(found_hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    print('Screenshot saved!')
else:
    print('Mario window not found')
