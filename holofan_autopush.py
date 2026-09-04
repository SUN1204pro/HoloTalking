"""One-command bridge: poll the backend for each new generated video and
auto-upload it into the Holoscope desktop app.

Talks to the backend over plain HTTP only (the API) -- no socket, no port 9999.
It polls  GET /api/latest_video  and, when the `version` changes, downloads
GET /api/latest_video/download  and drives Holoscope.

Run on the Windows OR macOS machine that has Holoscope installed:

    pip install pyautogui pillow opencv-python
    python holofan_autopush.py http://127.0.0.1:8000     # via the SSH tunnel
    python holofan_autopush.py 192.168.0.107             # or a bare IP (assumes :8000)

macOS only: System Settings -> Privacy & Security -> grant your terminal both
"Accessibility" and "Screen Recording", or clicks and image search do nothing.
Set HOLOSCOPE_WINDOW_HINT below to the exact app name shown in the menu bar.

  python holofan_autopush.py <url> --setup
      download the short freeze clip and transcode+Send it to the fan once
      (do this after picking an avatar in the browser)

  python holofan_autopush.py <url>
      poll loop: every new talking clip is transcoded + Sent to the fan

WINDOWS Holoscope (PD42 build) flow, all automated:
    Transcode -> file dialog (Ctrl+L, type full path, Enter)
    -> Start Transcode -> "File Name" dialog -> OK
    -> wait, scroll file list to bottom, click the new row -> Send
macOS (wrapped iOS app - the Photos picker is often broken, avoid).

MAXIMISE the Holoscope window and keep it maximised. If a click misses, tune the
coordinates with env vars (fractions of the window):
    HOLO_TRANSCODE_XY  HOLO_START_XY  HOLO_NAMEOK_XY  HOLO_NEWFILE_XY  HOLO_SEND_XY
    HOLO_TRANSCODE_WAIT (seconds to let transcoding finish, default 12)
Run at 100% display scaling.
"""
import os
import sys
import time
import threading

# Windows: become DPI-aware so pyautogui uses real pixels even when the display
# is scaled (Parallels often forces 200-250%). Without this, clicks land in a
# corner because logical != physical coordinates.
if sys.platform.startswith("win"):
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(HERE, "received_holofan_video.mp4")
HOLOSCOPE_WINDOW_HINT = "Holoscope"          # window title substring

# --- GUI automation ---------------------------------------------------------
try:
    import pyautogui
    pyautogui.FAILSAFE = True                # slam mouse to a corner to abort
    _GUI = True
except Exception as e:
    print(f"[autopush] pyautogui not available ({e}); will only RECEIVE, not upload.")
    _GUI = False

_upload_lock = threading.Lock()


def _click_image(name, timeout=15, confidence=0.8):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"missing button image: {name} (see setup notes in this file)")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            loc = pyautogui.locateCenterOnScreen(path, confidence=confidence)
        except Exception:
            loc = None
        if loc:
            pyautogui.click(loc)
            time.sleep(0.9)
            return
        time.sleep(0.5)
    raise TimeoutError(f"could not find {name} on screen")


def _holoscope_bounds():
    """(x, y, w, h) of the Holoscope window, or None."""
    if sys.platform.startswith("win"):
        try:
            wins = pyautogui.getWindowsWithTitle(HOLOSCOPE_WINDOW_HINT)
            if wins:
                w = wins[0]
                return (w.left, w.top, w.width, w.height)
        except Exception:
            pass
        return None
    if sys.platform != "darwin":
        return None
    import subprocess
    scr = f'''
    tell application "System Events"
        tell process "{HOLOSCOPE_WINDOW_HINT}"
            set p to position of window 1
            set s to size of window 1
            return (item 1 of p as text) & "," & (item 2 of p as text) & "," & (item 1 of s as text) & "," & (item 2 of s as text)
        end tell
    end tell
    '''
    try:
        out = subprocess.run(["osascript", "-e", scr], capture_output=True, text=True, timeout=5)
        x, y, w, h = (int(float(v)) for v in out.stdout.strip().split(","))
        return (x, y, w, h)
    except Exception:
        return None


def _minimize_console():
    """Get the terminal out of the way so clicks land on Holoscope, not on it."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)   # SW_MINIMIZE
            time.sleep(0.4)
    except Exception:
        pass


def _focus_holoscope():
    if sys.platform == "darwin":
        # macOS: focus via AppleScript (pygetwindow doesn't work here).
        import subprocess
        try:
            subprocess.run(
                ["osascript", "-e", f'tell application "{HOLOSCOPE_WINDOW_HINT}" to activate'],
                check=True, capture_output=True,
            )
            time.sleep(1.0)
            return True
        except Exception as e:
            print(f"[autopush] osascript focus failed: {e}")
            return False
    try:
        wins = pyautogui.getWindowsWithTitle(HOLOSCOPE_WINDOW_HINT)
        if wins:
            w = wins[0]
            if getattr(w, "isMinimized", False):
                w.restore()
            w.activate()
            time.sleep(1.0)
            return True
    except Exception as e:
        print(f"[autopush] focus failed: {e}")
    return False


def _click_or(name, rx, ry, wait, conf=0.7):
    """Click <name>.png if on screen, else click (rx, ry) as a fraction of the
    Holoscope window (falls back to whole screen if window bounds unknown)."""
    p = os.path.join(HERE, name)
    if os.path.exists(p):
        try:
            loc = pyautogui.locateCenterOnScreen(p, confidence=conf)
            if loc:
                pyautogui.click(loc); time.sleep(wait); return
        except Exception:
            pass
    b = _holoscope_bounds()
    if b:
        x, y, w, h = b
        pyautogui.click(x + int(w * rx), y + int(h * ry))
    else:
        sw, sh = pyautogui.size()
        pyautogui.click(int(sw * rx), int(sh * ry))
    time.sleep(wait)


# Windows Holoscope (PD42 build) click targets, as fractions of the MAXIMISED
# window. Override any of these with env vars if a click lands wrong, e.g.
#   $env:HOLO_TRANSCODE_XY="0.68,0.96"
def _xy(env, default):
    try:
        a, b = os.environ.get(env, default).split(",")
        return float(a), float(b)
    except Exception:
        return tuple(float(v) for v in default.split(","))

# Fractions of the MAXIMISED Holoscope window (measured from a 2814x1760 shot).
TRANSCODE_XY      = _xy("HOLO_TRANSCODE_XY",      "0.783,0.923")  # bottom bar "Transcode"
SEND_XY           = _xy("HOLO_SEND_XY",           "0.710,0.923")  # bottom bar "Send"
START_TRANSCODE_XY= _xy("HOLO_START_XY",          "0.470,0.900")  # green "Start Transcode" (bottom-right of the preview circle)
NAME_OK_XY        = _xy("HOLO_NAMEOK_XY",         "0.400,0.585")  # green "OK" on the File Name dialog
TRANSCODE_WAIT    = float(os.environ.get("HOLO_TRANSCODE_WAIT", "120"))  # seconds to let transcoding finish


def _abs(rx, ry):
    # On Windows the instruction is "maximise Holoscope", so use the full screen
    # -- pygetwindow's bounds aren't reliably DPI-consistent with pyautogui here.
    if sys.platform.startswith("win") or os.environ.get("HOLO_FULLSCREEN_COORDS"):
        sw, sh = pyautogui.size()
        return int(sw * rx), int(sh * ry)
    b = _holoscope_bounds()
    if b:
        x, y, w, h = b
        return x + int(w * rx), y + int(h * ry)
    sw, sh = pyautogui.size()
    return int(sw * rx), int(sh * ry)


def _upload_windows(video_path):
    """Windows Holoscope PD42 build (confirmed from screenshots):
        Transcode -> file dialog (Ctrl+L, type full path, Enter)
        -> preview -> Start Transcode -> "File Name" dialog -> OK
        -> wait for transcoding -> scroll file list to bottom -> click new row
        -> Send  (sends the selected file to the fan)

    Tune the coordinates via env vars (see top of file) if clicks miss.
    Maximise the Holoscope window and keep it maximised.
    """
    print("[autopush] Windows Holoscope: transcode + send ...")
    _minimize_console()                 # move the terminal out of the way
    _focus_holoscope()
    time.sleep(0.8)
    x, y = _abs(*TRANSCODE_XY)
    print(f"[autopush] screen={pyautogui.size()}  first click -> ({x},{y})")

    # 1. Transcode -> Windows file dialog
    pyautogui.click(*_abs(*TRANSCODE_XY)); time.sleep(1.8)

    # 2. file dialog: address bar (Ctrl+L) accepts a full FILE path -> opens it
    pyautogui.hotkey("ctrl", "l"); time.sleep(0.4)
    pyautogui.write(video_path, interval=0.004); time.sleep(0.3)
    pyautogui.press("enter"); time.sleep(2.2)

    # 3. preview -> Start Transcode
    pyautogui.click(*_abs(*START_TRANSCODE_XY)); time.sleep(1.2)

    # 4. "File Name" dialog -> OK (keep the auto-generated name)
    pyautogui.click(*_abs(*NAME_OK_XY)); time.sleep(1.0)

    # 5. wait for the transcode to finish (Holoscope auto-selects the new file)
    print(f"[autopush] transcoding (~{TRANSCODE_WAIT}s)...")
    time.sleep(TRANSCODE_WAIT)

    # 6. Send the (auto-selected, just-transcoded) file to the fan
    pyautogui.click(*_abs(*SEND_XY)); time.sleep(1.0)
    print("[autopush] Send clicked -- watch the fan.")


def _upload_mac(video_path):
    """macOS wrapped-iOS Holoscope: Transfer -> Video (Photos) -> newest -> 确认.
    Fragile -- the Photos picker is often broken in the wrapped app. Prefer Windows."""
    script = (
        f'set f to (POSIX file "{video_path}") as alias\n'
        'tell application "Photos"\n'
        '    import {f} skip check duplicates yes\n'
        'end tell\n'
    )
    import subprocess
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    time.sleep(2.0)
    _focus_holoscope()
    for name, rx, ry, wait in (
        ("transfer_btn.png", 0.82, 0.955, 1.4),
        ("video_btn.png",    0.50, 0.42,  2.0),
        ("first_thumb.png",  0.24, 0.21,  2.0),
        ("confirm_btn.png",  0.20, 0.64,  1.0),
    ):
        _click_or(name, rx, ry, wait)
    print("[autopush] upload triggered (mac) -- watch Holoscope.")


def upload_to_holoscope(video_path):
    if not _GUI:
        return
    with _upload_lock:
        try:
            if sys.platform.startswith("win"):
                _upload_windows(video_path)
            else:
                _upload_mac(video_path)
        except Exception as e:
            print(f"[autopush] upload failed: {e}")


# --- API polling ---------------------------------------------------------
import urllib.request

POLL_SECONDS = 2.0


def _http_json(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        import json
        return json.load(r)


def _download(url, dest, timeout=120):
    with urllib.request.urlopen(url, timeout=timeout) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)


FREEZE_FILE = os.path.join(HERE, "freeze.mp4")


def poll_loop(base_url):
    """Poll /api/latest_video; on each new talking clip, transcode + Send it to
    the fan (Holoscope shows the latest). Pure HTTP, no socket."""
    base_url = base_url.rstrip("/")
    print(f"[autopush] polling {base_url}/api/latest_video every {POLL_SECONDS}s ...")
    last_version = None
    while True:
        try:
            info = _http_json(f"{base_url}/api/latest_video")
            ver = info.get("version")
            if info.get("available") and ver != last_version:
                if last_version is not None:          # ignore the clip already there at startup
                    print(f"[autopush] new clip v={ver} ({info.get('duration')}s) -- downloading")
                    _download(f"{base_url}/api/latest_video/download", OUT_FILE)
                    upload_to_holoscope(OUT_FILE)
                last_version = ver
        except Exception as e:
            print(f"[autopush] poll error: {e}")
        time.sleep(POLL_SECONDS)


def setup_freeze(base_url, seconds=None):
    """One-shot: download the idle/freeze clip and transcode+Send it to the fan."""
    if seconds is None:
        try:
            seconds = int(os.environ.get("FREEZE_SECONDS", "5"))
        except ValueError:
            seconds = 5
    base_url = base_url.rstrip("/")
    url = f"{base_url}/api/freeze_video/download?seconds={seconds}"
    print(f"[setup] downloading freeze clip ({seconds}s) from {url}")
    _download(url, FREEZE_FILE)
    print(f"[setup] saved -> {FREEZE_FILE}")
    time.sleep(2)
    upload_to_holoscope(FREEZE_FILE)
    print("[setup] freeze clip transcoded + sent. Now run WITHOUT --setup and Generate.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--setup"]
    is_setup = "--setup" in sys.argv
    arg = args[0] if args else "http://127.0.0.1:8000"
    if not arg.startswith("http"):
        arg = f"http://{arg}:8000"        # allow just an IP for convenience
    print(f"[autopush] backend = {arg}   gui_upload = {_GUI}   mode = {'setup' if is_setup else 'poll'}")
    if is_setup:
        setup_freeze(arg)
    else:
        poll_loop(arg)
