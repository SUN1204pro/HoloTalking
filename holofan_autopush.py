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

Two fan playlist slots:
    slot 1 = FREEZE (idle avatar)      slot 2 = TALK (latest reply)

  python holofan_autopush.py <url> --setup
      build the 30s freeze clip and put it in slot 1 (do this once, after
      picking an avatar in the browser)

  python holofan_autopush.py <url>
      run the state loop: while idle/generating the fan shows slot 1; each new
      reply is uploaded to slot 2 and played for its duration, then back to slot 1.

WINDOWS (recommended - real file dialog):
    [tap slot] -> Truyền tải/Transfer -> type path -> Open
    -> Bắt đầu chuyển/Start transfer -> Xác nhận/Confirm -> % to 100
    switching which slot plays = one tap on that playlist row.
macOS (wrapped iOS app - the Photos picker is often broken, avoid).

Optional tight button crops next to this script (crop on the real screen):
    transfer_btn.png  start_transfer_btn.png  confirm_btn.png
    slot_1.png slot_2.png  slot_1_play.png slot_2_play.png
Without them it clicks window-relative fallback positions -- tune with env vars
HOLO_SLOT_X / HOLO_SLOT_Y0 / HOLO_SLOT_DY (fractions of the Holoscope window).
Run at a fixed resolution / 100% display scaling.
"""
import os
import sys
import time
import threading

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


# Playlist slots (middle column of the Windows Holoscope window). Row n's
# clickable area, as a fraction of the window. Tune SLOT_X / SLOT_Y0 / SLOT_DY
# with env vars if the click lands wrong.
SLOT_X   = float(os.environ.get("HOLO_SLOT_X",  "0.78"))
SLOT_Y0  = float(os.environ.get("HOLO_SLOT_Y0", "0.135"))   # centre of row 1
SLOT_DY  = float(os.environ.get("HOLO_SLOT_DY", "0.076"))   # row-to-row spacing


def _slot_point(n):
    return SLOT_X, SLOT_Y0 + (n - 1) * SLOT_DY


def _select_slot(n):
    """Click playlist row n so the next Transfer fills it / it becomes the one
    that plays."""
    rx, ry = _slot_point(n)
    _click_or(f"slot_{n}.png", rx, ry, 0.8)


def play_slot(n):
    """Switch what the fan shows to playlist slot n (one click, no file transfer)."""
    if not _GUI:
        return
    with _upload_lock:
        _focus_holoscope()
        time.sleep(0.3)
        rx, ry = _slot_point(n)
        _click_or(f"slot_{n}.png", rx, ry, 0.5)
        # click the row's play control (a bit right of the row label)
        _click_or(f"slot_{n}_play.png", min(0.86, rx + 0.06), ry, 0.4)
    print(f"[autopush] -> playing slot {n}")


def _upload_windows(video_path, slot=None):
    """Windows Holoscope 'Truyền tải / Transfer' flow (confirmed from screenshots):
        [select slot] -> Transfer -> Windows file dialog (type path, Open)
        -> trim screen -> 'Bắt đầu chuyển' (Start transfer)
        -> filename dialog -> 'Xác nhận' (Confirm)  -> progress to 100%

    Optional button PNGs next to this script (crop on the real Windows screen):
        transfer_btn.png  start_transfer_btn.png  confirm_btn.png  slot_1.png ...
    """
    print(f"[autopush] uploading via Windows Holoscope" + (f" (slot {slot})" if slot else "") + " ...")
    _focus_holoscope()
    time.sleep(0.6)

    if slot:
        _select_slot(slot)

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


def upload_to_holoscope(video_path, slot=None):
    if not _GUI:
        return
    with _upload_lock:
        try:
            if sys.platform.startswith("win"):
                _upload_windows(video_path, slot=slot)
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


# Which playlist slot holds which clip.
SLOT_FREEZE = int(os.environ.get("HOLO_SLOT_FREEZE", "1"))
SLOT_TALK   = int(os.environ.get("HOLO_SLOT_TALK",   "2"))
FREEZE_FILE = os.path.join(HERE, "freeze.mp4")


def poll_loop(base_url):
    """State machine: keep the fan on the FREEZE slot while idle / generating,
    switch to the TALK slot for the length of each new talking clip, then back.

      new clip rendered   -> upload it into SLOT_TALK, play SLOT_TALK for its duration
      is_generating / done -> play SLOT_FREEZE

    Only HTTP -- polls /api/latest_video (which also carries is_generating + duration).
    """
    base_url = base_url.rstrip("/")
    print(f"[autopush] state loop: freeze=slot {SLOT_FREEZE}, talk=slot {SLOT_TALK}, poll {POLL_SECONDS}s")
    last_version = None
    showing = None          # "freeze" | "talk"
    talk_until = 0.0

    def show(state, n):
        nonlocal showing
        if showing != state:
            play_slot(n)
            showing = state

    while True:
        now = time.time()
        try:
            info = _http_json(f"{base_url}/api/latest_video")
            ver = info.get("version")
            gen = info.get("is_generating")

            if info.get("available") and ver != last_version:
                if last_version is not None:
                    dur = float(info.get("duration") or 8.0)
                    print(f"[autopush] new clip v={ver} ({dur}s) -- downloading & sending to slot {SLOT_TALK}")
                    _download(f"{base_url}/api/latest_video/download", OUT_FILE)
                    upload_to_holoscope(OUT_FILE, slot=SLOT_TALK)      # blocking: does the Transfer dialog
                    play_slot(SLOT_TALK)
                    showing = "talk"
                    talk_until = time.time() + dur + 1.0
                last_version = ver

            elif showing == "talk" and now >= talk_until:
                show("freeze", SLOT_FREEZE)                            # talking clip finished
            elif gen:
                show("freeze", SLOT_FREEZE)                            # listening / rendering
            elif showing is None:
                show("freeze", SLOT_FREEZE)                            # first run
        except Exception as e:
            print(f"[autopush] poll error: {e}")
        time.sleep(POLL_SECONDS)


def setup_freeze(base_url, seconds=None):
    if seconds is None:
        try:
            seconds = int(os.environ.get("FREEZE_SECONDS", "5"))
        except ValueError:
            seconds = 5
    """One-shot: download the idle/freeze clip and upload it to Holoscope
    (put it in slot 1 of the fan playlist, then run without --setup for the
    talking clip in slot 2)."""
    base_url = base_url.rstrip("/")
    url = f"{base_url}/api/freeze_video/download?seconds={seconds}"
    print(f"[setup] downloading freeze clip ({seconds}s) from {url}")
    _download(url, FREEZE_FILE)
    print(f"[setup] saved -> {FREEZE_FILE}")
    print(f"[setup] uploading freeze clip into slot {SLOT_FREEZE}...")
    time.sleep(2)
    upload_to_holoscope(FREEZE_FILE, slot=SLOT_FREEZE)
    print(f"[setup] done. Freeze clip is in slot {SLOT_FREEZE}.")
    print("[setup] Now run WITHOUT --setup and generate in the browser --")
    print(f"[setup] talking clips go to slot {SLOT_TALK}, and the fan switches automatically.")


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
