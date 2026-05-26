"""Move a window to Virtual Desktop 2 by window title substring match."""
import sys
import time
import ctypes
import ctypes.wintypes

try:
    import pyvda
except ImportError:
    print("pyvda not installed — pip install pyvda")
    sys.exit(1)


def find_window_by_title(substring: str):
    """Find window handle by title substring."""
    result = []

    def enum_cb(hwnd, _):
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if substring.lower() in title.lower():
                result.append((hwnd, title))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    return result


def move_window_to_desktop(hwnd: int, desktop_number: int):
    """Move a window to the specified virtual desktop (1-indexed)."""
    desktops = pyvda.get_virtual_desktops()
    if desktop_number < 1 or desktop_number > len(desktops):
        print(f"Desktop {desktop_number} not found (have {len(desktops)} desktops)")
        return False

    target = desktops[desktop_number - 1]
    for attempt in range(3):
        try:
            app = pyvda.AppView(hwnd=hwnd)
            app.move(target)
            print(f"Moved window (hwnd={hwnd}) to Desktop {desktop_number}")
            return True
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            print(f"Failed to move window: {e}")
            return False


def main():
    title_search = sys.argv[1] if len(sys.argv) > 1 else "Mario"
    target_desktop = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    max_wait = int(sys.argv[3]) if len(sys.argv) > 3 else 30

    print(f"Looking for window matching '{title_search}'...")
    start = time.time()
    while time.time() - start < max_wait:
        windows = find_window_by_title(title_search)
        if windows:
            for hwnd, title in windows:
                print(f"Found: '{title}' (hwnd={hwnd})")
                move_window_to_desktop(hwnd, target_desktop)
            return
        time.sleep(1)

    print(f"No window matching '{title_search}' found after {max_wait}s")


if __name__ == "__main__":
    main()
