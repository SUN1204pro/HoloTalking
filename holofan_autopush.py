"""One-command Windows bridge: receive generated videos from the backend and
auto-upload each one into the Holoscope desktop app.

Run on the Windows PC that has Holoscope installed:

    pip install pyautogui pillow opencv-python
    python holofan_autopush.py 192.168.0.107        # <- backend LAN IP

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
    try:
        wins = pyautogui.getWindowsWithTitle(HOLOSCOPE_WINDOW_HINT)
        if wins:
            w = wins[0]
            if w.isMinimized:
                w.restore()
            w.activate()
            time.sleep(1.0)
            return True
    except Exception as e:
        print(f"[autopush] focus failed: {e}")
    return False


def upload_to_holoscope(video_path):
    if not _GUI:
        return
    with _upload_lock:
        print("[autopush] uploading to Holoscope...")
        try:
            if not _focus_holoscope():
                print("[autopush] Holoscope window not found -- is the app open? Skipping upload.")
                return
            _click_image("transfer_btn.png")
            _click_image("local_btn.png")
            time.sleep(1.2)                       # wait for the OS file dialog
            pyautogui.write(video_path, interval=0.01)
            pyautogui.press("enter")
            time.sleep(1.5)
            _click_image("upload_confirm.png")
            print("[autopush] upload triggered.")
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
