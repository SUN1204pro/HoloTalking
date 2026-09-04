# HoloTalking — restart runbook

Bring the whole stack back up after a disconnect / reboot. Three machines:

| Machine | Runs |
|---|---|
| **i86 GPU box** (SSH) | the backend `server_api.py` |
| **Mac** | SSH tunnel + frontend dev server |
| **Windows VM** (Parallels) | Holoscope + `holofan_autopush.py` (drives the fan) |

---

## 1. i86 — backend

```bash
ssh i86@14.161.44.216 -p 2223
cd ~/app/backend/SadTalker        # adjust if your path differs
tmux attach -t holo || tmux new -s holo
python server_api.py
```

Leave it in tmux so it survives the SSH drop. Detach with `Ctrl+b` then `d`.
Check it is up: `curl -s localhost:8000/api/health`

If port is stuck: `pkill -f server_api.py` then start again.

---

## 2. Mac — tunnel + frontend

```bash
cd ~/Documents/app
./start_holo_mac.sh
```

That opens: SSH tunnel (localhost:8000 -> i86), the frontend (http://localhost:5173),
and `holofan_autopush.py`. Ctrl+C stops all three.

Manual equivalent if the script fails:

```bash
ssh -N -L 8000:localhost:8000 i86@14.161.44.216 -p 2223 &
cd frontend && npm run dev -- --host
```

---

## 3. Windows VM — network + Holoscope + fan bridge

### 3a. Network (only if Holoscope shows Online: 0)

Mac must be joined to the fan Wi-Fi `3D-P…` (pw `12345678`).
In an **Admin** PowerShell:

```powershell
Enable-NetAdapter -Name "Ethernet"   -Confirm:$false
Enable-NetAdapter -Name "Ethernet 3" -Confirm:$false
Set-NetConnectionProfile -InterfaceIndex 2 -NetworkCategory Private
Set-NetConnectionProfile -InterfaceIndex 7 -NetworkCategory Private
New-NetFirewallRule -DisplayName "Fan LAN" -Direction Inbound -Action Allow -RemoteAddress 192.168.4.0/24
```

Check:

```powershell
ipconfig                 # want one 10.211.55.x  AND one 192.168.4.x
ping 192.168.4.1         # the fan must reply
```

Then open **Holoscope** and wait for `Online: 1`.

### 3b. SSH tunnel from the VM to the backend

In its own PowerShell window (leave it open):

```powershell
ssh -N -L 8000:localhost:8000 i86@14.161.44.216 -p 2223
```

Test: `curl.exe http://127.0.0.1:8000/api/health`  (use `curl.exe`, not `curl`)

### 3c. Fan bridge

```powershell
cd C:\Users\sunix\HoloTalking
git pull
```

**One-time per session** — seed the two clips into Holoscope's File List
(pick an avatar + generate one reply in the browser first):

```powershell
python holofan_autopush.py http://127.0.0.1:8000 --setup
```

**Then the live loop** — freeze while idle, motion clip while the avatar talks:

```powershell
$env:HOLO_SEND_ONLY="1"
python holofan_autopush.py http://127.0.0.1:8000
```

---

## Click coordinates (Holoscope, maximised)

Used literally as screen pixels. Override any with the env var, or re-measure
all at once with `python holofan_autopush.py --calibrate`.

| Button | Pixel | Env var |
|---|---|---|
| Send | `1950,1600` | `HOLO_SEND_XY` |
| Display | `2400,1600` | `HOLO_DISPLAY_XY` |
| Freeze row (list 1) | `2100,250` | `HOLO_FREEZE_ROW_XY` |
| Motion row (list 2) | `2100,300` | `HOLO_TALK_ROW_XY` |
| Freeze loop toggle | `2175,250` | `HOLO_FREEZE_LOOP_XY` |
| Motion loop toggle | `2175,300` | `HOLO_TALK_LOOP_XY` |
| Start Transcode | `1800,1500` | `HOLO_START_XY` |
| File Name box | `1407,800` | `HOLO_NAMEFIELD_XY` |
| OK (File Name dialog) | `1200,900` | `HOLO_NAMEOK_XY` |

Timing env vars: `HOLO_CLICK_PAUSE` (1s after each click), `HOLO_SETUP_WAIT`
(15s per clip in --setup), `HOLO_TRANSCODE_WAIT` (120s in the live transcode flow).
Debug: `HOLO_DRYRUN=1` (log clicks, don't move), `HOLO_KEEP_CONSOLE=1` (don't
minimise the terminal).

---

## Quick sanity checklist

1. i86: `curl -s localhost:8000/api/health` → JSON, `warming_up: false`
2. Mac: http://localhost:5173 loads, can pick an avatar
3. VM: `ping 192.168.4.1` replies, Holoscope `Online: 1`
4. VM: `curl.exe http://127.0.0.1:8000/api/health` → same JSON
5. VM: `--setup` once, then `HOLO_SEND_ONLY=1` loop running
