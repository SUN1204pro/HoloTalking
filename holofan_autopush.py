"""One-command Windows bridge: receive generated videos from the backend and
auto-upload each one into the Holoscope desktop app.

Run on the Windows OR macOS machine that has Holoscope installed:

    pip install pyautogui pillow opencv-python
    python holofan_autopush.py 192.168.0.107        # <- backend LAN IP

macOS only: System Settings -> Privacy & Security -> grant your terminal both
"Accessibility" and "Screen Recording", or clicks and image search do nothing.
Set HOLOSCOPE_WINDOW_HINT below to the exact app name shown in the menu bar.

What it does:
  1. Connects to the backend's socket streamer (port 9999) and saves every
     pushed MP4 to received_holofan_video.mp4 (overwritten each time).
  2. After each new video, drives the Holoscope window:
        Transfer -> Local -> (type the file path) -> Upload/confirm
     Clicks are anchored to button screenshots so they survive the app moving
     things around.

ONE-TIME SETUP -- put these PNGs next to this script (crop them from a Holoscope
screenshot; small tight crops of each button):
    transfer_btn.png     the "Transfer" button
    local_btn.png        the "Local" button/tab
    upload_confirm.png    the final upload/confirm button
Run Windows at a fixed resolution and 100% display scaling.
"""
import os
import sys
import time
import socket
import struct
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 9999
CHUNK = 64144
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
    """(x, y, w, h) of the Holoscope window on macOS, or None."""
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


def _import_to_photos(video_path):
    """Holoscope's 'Local' picker reads the macOS Photos library, not the disk.
    Import the freshly received video into Photos so it's the newest item."""
    script = f'''
    set f to POSIX file "{video_path}"
    tell application "Photos"
        import (f as alias list) skip check duplicates yes
    end tell
    '''
    import subprocess
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[autopush] Photos import failed: {r.stderr.strip()}")
        return False
    print("[autopush] imported to Photos")
    time.sleep(2.0)                                 # let Photos finish indexing
    return True


# Click targets as fractions of the Holoscope window (fixed phone-shaped window,
# so relative coords are reliable). Measured from the flow screenshots:
#   home screen  -> "Transfer" / "Truyền tải" : bottom-right of the bottom bar
#   popup        -> "Video"                    : centre, upper-middle
#   Photos picker-> first (newest) thumbnail   : top-left cell of the grid
#   edit screen  -> "确认" (green Confirm)      : lower-left of the card
_STEPS = [
    ("transfer_btn.png", 0.82, 0.955, 1.4),   # tap Transfer
    ("video_btn.png",    0.50, 0.42,  1.8),   # tap Video in the popup
    ("first_thumb.png",  0.25, 0.21,  1.8),   # tap newest video thumbnail
    ("confirm_btn.png",  0.20, 0.64,  1.0),   # tap 确认 / Confirm
]


def _tap(name, rx, ry, wait):
    """Click `name`.png if it's on screen, else click (rx, ry) inside the window."""
    path = os.path.join(HERE, name)
    if os.path.exists(path):
        try:
            loc = pyautogui.locateCenterOnScreen(path, confidence=0.7)
            if loc:
                pyautogui.click(loc)
                time.sleep(wait)
                return
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


def upload_to_holoscope(video_path):
    """Holoscope 'Video' flow (from the flow screenshots):
        Transfer -> Video -> Photos picker (newest thumbnail) -> 确认 -> fan

    Received clip is imported to Photos first so it's the top-left thumbnail.
    Each step tries an image match (<name>.png next to this script) and falls
    back to a window-relative click. Provide the PNGs for best reliability:
        transfer_btn.png  video_btn.png  first_thumb.png  confirm_btn.png
    """
    if not _GUI:
        return
    with _upload_lock:
        print("[autopush] uploading to Holoscope...")
        try:
            _import_to_photos(video_path)
            if not _focus_holoscope():
                print("[autopush] Holoscope window not found -- open it & connect the fan. Skipping.")
                return
            for name, rx, ry, wait in _STEPS:
                _tap(name, rx, ry, wait)
            print("[autopush] upload triggered -- watch Holoscope for the progress bar / File count.")
        except Exception as e:
            print(f"[autopush] upload failed: {e}")


# --- socket receiver -------------------------------------------------------
def receive_loop(server_ip):
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((server_ip, PORT))
            print(f"[autopush] connected to {server_ip}:{PORT}, waiting for videos...")
            while True:
                header = b""
                while len(header) < 8:
                    chunk = s.recv(8 - len(header))
                    if not chunk:
                        raise ConnectionError("server closed")
                    header += chunk
                size = struct.unpack("!Q", header)[0]
                if size == 0:
                    continue
                got = 0
                with open(OUT_FILE, "wb") as f:
                    while got < size:
                        chunk = s.recv(min(CHUNK, size - got))
                        if not chunk:
                            raise ConnectionError("server closed mid-transfer")
                        f.write(chunk)
                        got += len(chunk)
                print(f"[autopush] received {got} bytes -> {OUT_FILE}")
                threading.Thread(target=upload_to_holoscope, args=(OUT_FILE,), daemon=True).start()
        except Exception as e:
            print(f"[autopush] connection error: {e}. Reconnecting in 3s...")
            time.sleep(3)


if __name__ == "__main__":
    ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    print(f"[autopush] backend = {ip}   gui_upload = {_GUI}")
    receive_loop(ip)
