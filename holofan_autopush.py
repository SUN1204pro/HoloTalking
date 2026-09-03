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
  2. After each new video, drives Holoscope to upload it to the fan.

     WINDOWS (recommended - real file dialog):
        Truyền tải / Transfer -> type the file path -> Open
        -> Bắt đầu chuyển / Start transfer -> Xác nhận / Confirm -> % to 100
     macOS (wrapped iOS app - the Photos picker is often broken, avoid):
        Transfer -> Video -> newest Photos item -> 确认

ONE-TIME SETUP -- optional tight button crops next to this script make it robust:
    WINDOWS:  transfer_btn.png  start_transfer_btn.png  confirm_btn.png
    macOS:    transfer_btn.png  video_btn.png  first_thumb.png  confirm_btn.png
Run at a fixed resolution / 100% display scaling. Without the PNGs it clicks
window-relative fallback positions (tune the fractions in the code if off).
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


def _upload_windows(video_path):
    """Windows Holoscope 'Truyền tải / Transfer' flow (confirmed from screenshots):
        Transfer -> Windows file dialog (type path, Open)
        -> trim screen -> 'Bắt đầu chuyển' (Start transfer)
        -> filename dialog -> 'Xác nhận' (Confirm)  -> progress to 100%

    Optional button PNGs next to this script (crop on the real Windows screen):
        transfer_btn.png  start_transfer_btn.png  confirm_btn.png
    """
    print("[autopush] uploading via Windows Holoscope...")
    _focus_holoscope()
    time.sleep(0.6)

    # 1. open the Transfer file dialog (bottom bar, centre-ish)
    _click_or("transfer_btn.png", 0.74, 0.95, 1.6)

    # 2. Windows file-open dialog: the "File name" box already has focus.
    #    Select-all (in case of leftover text), type the full path, Enter = Open.
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.write(video_path, interval=0.005)
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(2.0)

    # 3. trim/preview screen -> "Bắt đầu chuyển" (Start transfer), green, bottom-right
    _click_or("start_transfer_btn.png", 0.88, 0.90, 1.5)

    # 4. filename dialog -> "Xác nhận" (Confirm), left button
    _click_or("confirm_btn.png", 0.47, 0.63, 1.0)

    print("[autopush] transfer started -- watch the % bar in Holoscope.")


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
