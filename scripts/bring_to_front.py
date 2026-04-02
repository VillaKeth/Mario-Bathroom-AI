import ctypes
import ctypes.wintypes
import time
import pyautogui

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
        if 'Mario AI' in title and 'Visual Studio' not in title:
            found_hwnd = hwnd
            print(f'Found: {title} hwnd={hwnd}')
    return True

user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

if found_hwnd:
    user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(found_hwnd)
    user32.MoveWindow(found_hwnd, 50, 50, 820, 640, True)
    time.sleep(1.5)
    img = pyautogui.screenshot(region=(50, 50, 820, 640))
    img.save('screenshot_mario_front.png')
    print('Screenshot saved!')
else:
    print('Mario window not found')
