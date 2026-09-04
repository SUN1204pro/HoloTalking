# Holo fan — connect checklist

How to get Holoscope (in the Parallels Windows VM) to see the fan: **`Online: 1`**.

## How it fits together

```
Holo fan  --Wi-Fi hotspot "3D-P..."-->  Mac Wi-Fi
                                          |  (Parallels 2nd adapter, BRIDGED to Wi-Fi)
                                          v
                              Windows VM "Ethernet 3"  192.168.4.x
                              Windows VM "Ethernet"    10.211.55.x  (Shared -> internet + SSH tunnel)

Fan connects OUT to Holoscope on TCP 6666. Holoscope has no API -- discovery is
UDP broadcast on the 192.168.4.0/24 subnet, so that adapter must be reachable
and NOT blocked by Windows Firewall.
```

Fan Wi-Fi: SSID `3D-P…`   password `12345678`   fan IP `192.168.4.1`

---

## 1. Mac — join the fan Wi-Fi

System Settings → Wi-Fi → join `3D-P…` (pw `12345678`).
"No internet" is normal — the Mac keeps internet via the Parallels Shared network
or a second connection; the fan Wi-Fi is only for the fan.

## 2. Parallels — give the VM a bridged adapter (one-time)

VM must be **shut down** (not suspended).

1. Parallels → the VM → **Configure** → **Hardware** tab.
2. Keep **Network 1 = Shared Network** (internet + SSH).
3. Click **+** (bottom-left) → **Network** → add **Network 2**.
4. Set Network 2 **Source = Wi-Fi**  (this bridges it onto the fan Wi-Fi).
5. Also set Parallels mouse mode: VM → Configure → **Hardware → Mouse & Keyboard
   → "Optimize for games"** (so `holofan_autopush.py` clicks land).
6. Boot the VM.

## 3. Windows VM — enable + trust both adapters

Admin PowerShell (Start → type "powershell" → Ctrl+Shift+Enter):

```powershell
Enable-NetAdapter -Name "Ethernet"   -Confirm:$false
Enable-NetAdapter -Name "Ethernet 3" -Confirm:$false

# find the interface indexes
Get-NetConnectionProfile

# mark BOTH Private (replace 2 / 7 with the InterfaceIndex values above)
Set-NetConnectionProfile -InterfaceIndex 2 -NetworkCategory Private
Set-NetConnectionProfile -InterfaceIndex 7 -NetworkCategory Private

# allow the fan subnet through the firewall
New-NetFirewallRule -DisplayName "Fan LAN" -Direction Inbound -Action Allow -RemoteAddress 192.168.4.0/24
```

## 4. Verify

```powershell
ipconfig
```

Expect **two** adapters:
- one `10.211.55.x`  (Shared — has a Default Gateway `10.211.55.2`)
- one `192.168.4.x`  (fan — no gateway, that's fine)

```powershell
ping 192.168.4.1
```

Must reply. If it does not: Mac is not on the fan Wi-Fi, or the bridged adapter
source is not "Wi-Fi", or the VM needs a reboot.

## 5. Open Holoscope → wait for `Online: 1`

Still `Online: 0` even though `ping 192.168.4.1` works → the firewall is still
blocking discovery. Test by turning it off briefly:

```powershell
Set-NetFirewallProfile -Profile Private,Public -Enabled False   # restart Holoscope
# if it now shows Online: 1, turn it back on and keep the "Fan LAN" rule:
Set-NetFirewallProfile -Profile Private,Public -Enabled True
```

If discovery still prefers the wrong adapter, make the fan adapter win
(replace indexes with yours):

```powershell
Set-NetIPInterface -InterfaceIndex 7 -InterfaceMetric 1
Set-NetIPInterface -InterfaceIndex 2 -InterfaceMetric 50
```

Restart Holoscope again.

---

## After a reboot (fast path)

1. Mac still on `3D-P…` Wi-Fi? (rejoin if not)
2. VM PowerShell:
   ```powershell
   ping 192.168.4.1
   ```
3. Open Holoscope → `Online: 1`.
4. Adapters/firewall/profile settings persist — you normally do **not** redo
   step 3 unless Windows reset a profile to Public (check with
   `Get-NetConnectionProfile`).
