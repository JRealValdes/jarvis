# Headless Raspberry Pi ops

Run Jarvis on a Raspberry Pi **without** a monitor or keyboard. Day-to-day work is from your PC on the home LAN via **SSH** (a remote terminal — not a full remote desktop).

Related issues: **#29** (this guide), **#28** (voice / Home Assistant on the same Pi), **#31** (off-LAN API via **Tailscale**; named Cloudflare Tunnel is a documented alternative only). The API is LAN-only from Jarvis itself; do not port-forward `:8000` or SSH.

**Runtime model for this issue:** systemd + `uv run jarvis api` (lightweight on older boards such as a Pi 3). Docker Compose beside Home Assistant remains a later option when you co-host HA (#28).

Keep the Pi **powered on 24/7**. A smart plug is useful for a last-resort hard power-cycle if SSH is dead — not for a daily on/off schedule (unclean cuts risk SD card corruption). Prefer `sudo poweroff` over SSH before cutting power when you can.

Cursor agents: use the project skill **`raspberry-pi-ops`** when the operator asks to update the Pi / Jarvis Server or sync secrets.

---

## Prerequisites (operator PC)

- Same Wi‑Fi / LAN as the Pi
- OpenSSH client (`ssh`, `scp`) — included with current Windows 10/11, macOS, and Linux
- This repo cloned locally, with secrets already working on the PC (`.env`, optional Google OAuth / user YAML)
- [uv](https://docs.astral.sh/uv/) on the PC (for running the deploy helpers)

---

## Architecture note (Pi 3 and `sqlite-vec`)

Jarvis depends on `langgraph-checkpoint-sqlite`, which requires **`sqlite-vec`**. Published wheels exist for **`aarch64`** (and x86_64), **not** for 32-bit `armv7l`.

On a Raspberry Pi 3 (or any board that might boot 32-bit by default):

1. Flash **Raspberry Pi OS Lite (64-bit)** via [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. After first boot, confirm: `uname -m` → must be **`aarch64`** (not `armv7l`).
3. Only then run `uv sync` on the Pi.

Imager tips: keep **Exclude system drives** checked; leave **Raspberry Pi Connect** off for this LAN/SSH setup.

---

## First setup

### 1. Flash the Pi (one-time)

1. Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Device: your Pi model (e.g. Raspberry Pi 3).
3. OS: **Raspberry Pi OS Lite (64-bit)**.
4. In Imager **OS customisation**:
   - Hostname (e.g. `jarvis-raspberry`)
   - Username / password (e.g. `jreal`)
   - Wi‑Fi SSID, password, country
   - **Enable SSH**
5. Flash, insert the card, power on, wait ~1–2 minutes.

**Host identity after a re-flash:** the Pi gets a new SSH host key. On the PC, if you see `REMOTE HOST IDENTIFICATION HAS CHANGED`, remove the old entry and reconnect:

```powershell
ssh-keygen -R jarvis-raspberry.local
ssh-keygen -R 192.168.x.x
ssh USER@HOST
```

**mDNS vs IP:** `hostname.local` sometimes works on Windows and sometimes does not. Prefer a stable **DHCP reservation** in the router for the Pi, and put that IPv4 in `deploy/pi.local.env` as `JARVIS_PI_HOST` if `.local` is flaky.

### 2. SSH key auth (strongly recommended)

Deploy scripts default to **BatchMode** (no password prompts). Set up a key once.

On the PC (PowerShell):

```powershell
# If you do not already have a key:
ssh-keygen -t ed25519 -C "jarvis-pi"

# Install the public key on the Pi (enter the account password once):
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh USER@PI_HOST "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

# Verify (should not ask for the account password):
ssh USER@PI_HOST
```

Optional: key passphrase + Windows ssh-agent so you unlock once per login session.

### 3. Passwordless sudo for `jarvis.service` only

Unattended `update_code.py` / `sync_secrets.py --restart` run `sudo systemctl … jarvis.service`. Allow that without a password (narrow sudoers drop-in on the Pi):

```bash
sudo visudo -f /etc/sudoers.d/jarvis-systemctl
```

Contents (adjust `jreal` if needed):

```
jreal ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop jarvis.service, /usr/bin/systemctl start jarvis.service, /usr/bin/systemctl restart jarvis.service, /usr/bin/systemctl status jarvis.service, /usr/bin/systemctl is-active jarvis.service
```

```bash
sudo chmod 440 /etc/sudoers.d/jarvis-systemctl
sudo systemctl is-active jarvis.service   # should not prompt after the unit exists
```

**Firewall:** on a home LAN, default Pi OS is usually fine. Do not port-forward SSH (22) or the Jarvis API to the public internet; use [Tailscale (off-LAN)](#off-lan-access-tailscale-31) instead.

### 4. Install uv and clone Jarvis on the Pi

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
mkdir -p ~/Desktop/Stark_Industries   # or any path you prefer
cd ~/Desktop/Stark_Industries
git clone --branch main https://github.com/JRealValdes/jarvis.git
cd jarvis
uname -m    # aarch64
uv sync
```

During feature work you may clone a `feature/…` branch instead of `main`. Private runtime files are **not** in git — push them from the PC next.

### 5. Point the PC at the Pi

```bash
cp deploy/pi.env.example deploy/pi.local.env
```

Example:

```env
JARVIS_PI_USER=jreal
JARVIS_PI_HOST=192.168.68.54
JARVIS_PI_DIR=/home/jreal/Desktop/Stark_Industries/jarvis
```

`pi.local.env` is gitignored.

### 6. Sync secrets with the PC

```bash
uv run python deploy/sync_secrets.py --dry-run
uv run python deploy/sync_secrets.py --restart
```

By default this **pushes** catalog files local → Pi. Limit groups with `--only`. Use `--allow-password` only if key auth is not ready yet.

**Pull** (Pi → PC), e.g. after editing LinkedIn prefs on the server:

```bash
uv run python deploy/sync_secrets.py --pull --only user-prefs --dry-run
uv run python deploy/sync_secrets.py --pull --only user-prefs
```

**Conflicts:** the script stores last-sync content hashes in `deploy/.secrets_sync_state.json` (gitignored). If both sides changed since the last sync, it **aborts**, lists paths, and prints local/remote modification times plus a newer-mtime hint (clocks may skew; never used to auto-resolve). Re-run with `--force-local` or `--force-remote` (and `--only`) after you decide which side wins. There is no automatic merge.

Group policies live in `deploy/secret_paths.py` (`push` vs `sync`). `--list-groups` prints each group and its policy.

### 7. Install the systemd service on the Pi

Edit `deploy/jarvis.service` so `User=`, `Group=`, `WorkingDirectory=`, and `ExecStart=` match your account and paths, then:

```bash
sudo cp deploy/jarvis.service /etc/systemd/system/jarvis.service
sudo systemctl daemon-reload
sudo systemctl enable --now jarvis.service
systemctl status jarvis.service
```

Smoke test from the PC browser: `http://PI_IP:8000/docs`.

**Reboot test (do this once):** `sudo reboot`, wait for the Pi to return, confirm `/docs` without starting Jarvis by hand.

---

## Day-to-day updates (from the PC)

### Update application code

After the commits the Pi should run are on the remote the Pi tracks:

```bash
uv run python deploy/update_code.py --dry-run
uv run python deploy/update_code.py
```

Remote flow: **stop** `jarvis` → `git pull --ff-only` → `uv sync` → **start** → health-check `http://127.0.0.1:8000/docs`. If pull or sync fails, the script attempts to start the service again so the API is not left down on purpose.

### Update secrets only

```bash
uv run python deploy/sync_secrets.py --restart
# Retrieve live prefs from the Pi:
uv run python deploy/sync_secrets.py --pull --only user-prefs
```

### Manual SSH

```bash
ssh USER@PI_HOST
sudo systemctl status jarvis
sudo journalctl -u jarvis -n 80 --no-pager
```

---

## Adding a new secret / runtime file

`sync_secrets.py` only copies paths listed in **`deploy/secret_paths.py`**. When you introduce a new Pi-bound file:

1. Add it to `SECRET_GROUPS` or `SECRET_GLOBS` in the same PR/commit.
2. Update README “Local runtime assets” if operators need to know.
3. Add/adjust a test under `tests/test_deploy_secret_paths.py` when the pattern is non-obvious.

Cursor rule: `pi-secrets-catalog`. Skill: `raspberry-pi-ops`.

---

## Web search rate limits

`web_search_tool` searches with the `ddgs` package (no API key). Providers often rate-limit or block a shared or home IP. On the Pi this shows up as an intermittent `DDGSException: No results found.` even when the same query works from a desktop. Jarvis retries with a short backoff and alternate backends, then returns an error that names `ddgs`, the exception type, the backends tried, and a hint. That error is not a successful empty search (`No search results.`).

If lookups fail for a long stretch, wait and retry. Check `journalctl -u jarvis` for `ddgs search failed`. No paid search API is required.

---

## Voice / Home Assistant (#28)

Voice bridges and HA should talk to Jarvis on **localhost or LAN**. They do not need a public URL or Tailscale.

---

## Off-LAN access (Tailscale) (#31)

Jarvis does **not** open a tunnel inside the Python process. Off-LAN reachability is a **host** concern: install [Tailscale](https://tailscale.com/) on the Pi and on each client, join the same tailnet, then point clients at the Pi’s MagicDNS name or Tailscale IP (same API port as on the LAN, default `8000`).

Auth stays Jarvis JWT (or future device tokens). Tailscale only solves **reachability**.

Frontend: configure the API base URL in `jarvis_app` Settings (see [jarvis_app#11](https://github.com/JRealValdes/jarvis_app/issues/11)). Do not embed a Tailscale SDK in the app.

### 1. Pi — install and stay online

On the Pi (official install; package provides `tailscaled` via systemd — we do **not** ship a custom unit under `deploy/`):

```bash
# Follow https://tailscale.com/download/linux for the current one-liner / apt steps
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale status
tailscale ip -4    # e.g. 100.x.y.z
```

Confirm the daemon is enabled across reboots:

```bash
systemctl is-enabled tailscaled
systemctl status tailscaled --no-pager
```

Optional: set a stable MagicDNS hostname in the [Tailscale admin console](https://login.tailscale.com/admin/machines) (e.g. `jarvis-pi`) so clients use `http://jarvis-pi:8000` instead of remembering `100.x`.

`jarvis.service` is unchanged: it still binds `0.0.0.0:API_PORT` on the Pi. Tailscale routes private traffic to that listener.

### 2. Phone / laptop — same tailnet + auto-connect

1. Install the Tailscale app for the OS.
2. Sign in to the **same** tailnet as the Pi (invite the account, or use a shared tag / ACL as you prefer).
3. Enable **auto-connect** / **always-on VPN** / **connect on demand** (wording varies by OS) so the VPN stays up without opening the Tailscale app each time.
4. Smoke-test in a browser or with curl while **off** the home Wi‑Fi (mobile data): `http://<magicdns-or-100.x>:8000/docs`.

Day-to-day: open Jarvis (or any client), leave Tailscale connected in the background. If the VPN is down, the API is unreachable — same as being off the LAN without a mesh.

### 3. Friends / intimate circle

Invite them to the tailnet (or a restricted ACL tag that can only reach the Pi’s API). They install Tailscale, enable auto-connect, and set the same base URL in the app. You do **not** WhatsApp a changing public URL.

### 4. SSH from outside (bonus)

The same mesh can carry SSH (`ssh USER@jarvis-pi` or `USER@100.x.y.z`) without router port-forward. Deploy helpers (`deploy/pi.local.env`) can keep using the LAN IP at home; off-LAN, point `JARVIS_PI_HOST` at MagicDNS / Tailscale IP when you need PC → Pi scripts from away.

### Alternative: named Cloudflare Tunnel

If you need a stable **public** `https://…` hostname and no VPN app on the phone: run account-backed `cloudflared` on the Pi (host service), map a hostname under your Cloudflare DNS domain to `http://localhost:8000`, and put that HTTPS URL in the client. Domain registration is typically a small yearly cost; Tunnel on Cloudflare Free / Zero Trust Free is usually $0 for personal use.

Prefer Tailscale for this project’s default. Do **not** use ephemeral `*.trycloudflare.com` quick tunnels or publish URLs via Firebase/Telegram. Do **not** put tunnel logic back inside the Jarvis process.

---

## What not to do on the Pi

| Avoid | Why |
|-------|-----|
| 32-bit OS (`armv7l`) on Pi 3 | `sqlite-vec` has no wheel; use 64-bit (`aarch64`) |
| Router port-forward of SSH or `:8000` | Use Tailscale (#31); named tunnel only if you chose that alternative |
| Daily smart-plug power cuts | Unclean shutdowns; leave the Pi on |
| Jarvis-in-process / quick tunnels | Removed in #30; host-layer Tailscale (or named tunnel) only |

---

## Helper reference

See [deploy/README.md](../deploy/README.md). Secret groups: `deploy/secret_paths.py`.
