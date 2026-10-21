# Headless Raspberry Pi ops

Run Jarvis on a Raspberry Pi **without** a monitor or keyboard. Day-to-day work is from your PC on the home LAN via **SSH** (a remote terminal — not a full remote desktop).

Related issues: **#29** (this guide), **#28** (voice / Home Assistant on the same Pi), **#31** (off-LAN API). Legacy public exposure (`JARVIS_EXPOSE_API_WITH_CLOUDFLARED`, Firebase, Telegram URL publish) stays **off** on the Pi; see **#30**.

**Runtime model for this issue:** systemd + `uv run jarvis api` (lightweight on older boards such as a Pi 3). Docker Compose beside Home Assistant remains a later option when you co-host HA (#28).

Keep the Pi **powered on 24/7**. A smart plug is useful for a last-resort hard power-cycle if SSH is dead — not for a daily on/off schedule (unclean cuts risk SD card corruption). Prefer `sudo poweroff` over SSH before cutting power when you can.

Cursor agents: use the project skill **`raspberry-pi-ops`** when the operator asks to update the Pi / Jarvis Server or sync secrets.

---

## Prerequisites (operator PC)

- Same Wi‑Fi / LAN as the Pi
- OpenSSH client (`ssh`, `scp`) — included with current Windows 10/11, macOS, and Linux
- This repo cloned locally, with secrets already working on the PC (`.env`, optional Google/Firebase/user YAML)
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

**Firewall:** on a home LAN, default Pi OS is usually fine. Do not port-forward SSH (22) or the Jarvis API to the public internet; use #31 later for remote access.

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

### 6. Push secrets from the PC

```bash
uv run python deploy/sync_secrets.py --dry-run
uv run python deploy/sync_secrets.py --restart
```

By default this copies every **existing** local file in the catalog. Limit groups with `--only`. Use `--allow-password` only if key auth is not ready yet.

On the Pi `.env`, keep:

```env
JARVIS_EXPOSE_API_WITH_CLOUDFLARED=0
```

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

## Voice / Home Assistant (#28)

Voice bridges and HA should talk to Jarvis on **localhost or LAN**. They do not need a public URL.

---

## What not to do on the Pi

| Avoid | Why |
|-------|-----|
| 32-bit OS (`armv7l`) on Pi 3 | `sqlite-vec` has no wheel; use 64-bit (`aarch64`) |
| `JARVIS_EXPOSE_API_WITH_CLOUDFLARED=1` | Legacy quick tunnel; see #30 / #31 |
| Router port-forward of SSH or `:8000` | Use Tailscale/named tunnel (#31) later |
| Daily smart-plug power cuts | Unclean shutdowns; leave the Pi on |

---

## Helper reference

See [deploy/README.md](../deploy/README.md). Secret groups: `deploy/secret_paths.py`.
