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


def upload_to_holoscope(video_path):
    """Holoscope 'Local' flow (from the app manual):
        Transfer -> Local (Địa phương) -> pick the video file -> Confirm -> upload

    Button screenshots needed next to this script (crop tight on the actual Mac):
        transfer_btn.png   the "Transfer" / "Truyền tải" button (bottom bar)
        local_btn.png      the "Địa phương" (folder) button in the Transfer popup
        confirm_btn.png    the confirm/OK button after selecting the file
    In the macOS file picker the script presses Cmd+Shift+G and types the folder,
    then Return twice (open folder, then the file must already be selected/typed).
    If your picker layout differs, screenshot it and tell me.
    """
    if not _GUI:
        return
    with _upload_lock:
        print("[autopush] uploading to Holoscope...")
        try:
            if not _focus_holoscope():
                print("[autopush] Holoscope window not found -- is the app open & connected to the fan? Skipping.")
                return
            _click_image("transfer_btn.png")
            _click_image("local_btn.png", timeout=8)
            time.sleep(1.5)                        # file picker opens

            # macOS "go to folder" then type the filename
            folder = os.path.dirname(video_path)
            fname = os.path.basename(video_path)
            pyautogui.hotkey("command", "shift", "g")
            time.sleep(0.6)
            pyautogui.write(folder + "/", interval=0.01)
            pyautogui.press("return")
            time.sleep(0.8)
            pyautogui.write(fname, interval=0.01)  # jumps to the file in the list
            time.sleep(0.4)
            pyautogui.press("return")             # open/select it
            time.sleep(1.2)

            try:
                _click_image("confirm_btn.png", timeout=6)
            except Exception:
                pyautogui.press("return")         # some builds auto-confirm
            print("[autopush] upload triggered -- watch Holoscope for the progress bar.")
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
