# Headless Raspberry Pi ops

Run Jarvis on a Raspberry Pi **without** a monitor or keyboard. Day-to-day work is from your PC on the home LAN via **SSH** (a remote terminal — not a full remote desktop).

Related issues: **#29** (this guide), **#28** (voice / Home Assistant on the same Pi), **#31** (off-LAN API). Legacy public exposure (`JARVIS_EXPOSE_API_WITH_CLOUDFLARED`, Firebase, Telegram URL publish) stays **off** on the Pi; see **#30**.

**Runtime model for this issue:** systemd + `uv run jarvis api` (lightweight on older boards such as a Pi 3). Docker Compose beside Home Assistant remains a later option when you co-host HA (#28).

Keep the Pi **powered on 24/7**. A smart plug is useful for a last-resort hard power-cycle if SSH is dead — not for a daily on/off schedule (unclean cuts risk SD card corruption). Prefer `sudo poweroff` over SSH before cutting power when you can.

---

## Prerequisites (operator PC)

- Same Wi‑Fi / LAN as the Pi
- OpenSSH client (`ssh`, `scp`) — included with current Windows 10/11, macOS, and Linux
- This repo cloned locally, with secrets already working on the PC (`.env`, optional Google/Firebase/user YAML)
- [uv](https://docs.astral.sh/uv/) on the PC (for running the deploy helpers)

---

## First setup

### 1. Flash the Pi (one-time, may need a display or Imager-only)

1. Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Choose Raspberry Pi OS (Lite is enough for headless).
3. In Imager **OS customisation**:
   - Set hostname, username, and password
   - Configure Wi‑Fi (SSID + password) if you will not use Ethernet
   - **Enable SSH** (prefer public-key; you can also enable password and switch to keys next)
4. Flash the card, insert it, power the Pi, wait ~1–2 minutes.

Find the Pi on the LAN (router DHCP list, or try `ping <hostname>.local`).

### 2. SSH key auth from your PC

On the PC (PowerShell or a Unix shell):

```bash
# If you do not already have a key:
ssh-keygen -t ed25519 -C "jarvis-pi"

# Copy the public key (Windows OpenSSH):
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh USER@PI_HOST "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

Then:

```bash
ssh USER@PI_HOST
```

You should land in a shell on the Pi without typing the account password (key unlock may still prompt for your key passphrase).

Optional hardening on the Pi (after keys work): disable password login in `/etc/ssh/sshd_config` (`PasswordAuthentication no`), then `sudo systemctl restart ssh`.

**Firewall:** on a home LAN, default Pi OS is usually fine. Do not port-forward SSH (22) or the Jarvis API to the public internet; use #31 later for remote access.

### 3. Install uv and clone Jarvis on the Pi

Still on the Pi over SSH:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# open a new SSH session or source the uv env, then:
cd ~
git clone https://github.com/JRealValdes/jarvis.git
cd jarvis
uv sync
```

Use SSH deploy keys or HTTPS as you prefer. Private runtime files are **not** in git — push them from the PC in the next step.

### 4. Point the PC at the Pi

On the PC, in this repo:

```bash
cp deploy/pi.env.example deploy/pi.local.env
```

Edit `deploy/pi.local.env`:

```env
JARVIS_PI_USER=pi
JARVIS_PI_HOST=192.168.1.50
JARVIS_PI_DIR=/home/pi/jarvis
```

`pi.local.env` is gitignored.

### 5. Push secrets from the PC

```bash
uv run python deploy/sync_secrets.py --dry-run
uv run python deploy/sync_secrets.py
```

By default this copies every **existing** local file in the catalog (`.env`, `data/users.db`, Firebase key, user preference YAML, Google OAuth secrets, optional MCP config). Limit groups with `--only`:

```bash
uv run python deploy/sync_secrets.py --only env
uv run python deploy/sync_secrets.py --only env,user-prefs,google
uv run python deploy/sync_secrets.py --list-groups
```

Files on the Pi are set to mode `600`.

On the Pi `.env`, keep:

```env
JARVIS_EXPOSE_API_WITH_CLOUDFLARED=0
```

LAN-only is enough: Home Assistant / voice (#28) should call `http://127.0.0.1:8000` (or the Pi LAN IP), not a Cloudflare quick tunnel.

### 6. Install the systemd service on the Pi

On the Pi, edit `deploy/jarvis.service` so `User=`, `WorkingDirectory=`, and `ExecStart=` match your account and uv path, then:

```bash
sudo cp deploy/jarvis.service /etc/systemd/system/jarvis.service
sudo systemctl daemon-reload
sudo systemctl enable --now jarvis.service
systemctl status jarvis.service
```

Check the API on the Pi:

```bash
curl -s http://127.0.0.1:8000/docs
```

From another LAN device, use `http://PI_HOST:8000` only if you intentionally bind/listen for LAN clients (uvicorn defaults are fine for local + reverse proxy later).

---

## Day-to-day updates (from the PC)

### Update application code

After you push commits to GitHub (or otherwise update `origin` that the Pi tracks):

```bash
uv run python deploy/update_code.py --dry-run
uv run python deploy/update_code.py
```

That SSHs to the Pi and runs `git pull --ff-only`, `uv sync`, and `sudo systemctl restart jarvis.service`.

Skip restart: `--no-restart`.

### Update secrets only

Change `.env` or credential files on the PC, then:

```bash
uv run python deploy/sync_secrets.py
# optional: restart so processes reload env
uv run python deploy/update_code.py --no-restart
ssh USER@HOST "sudo systemctl restart jarvis.service"
```

(`sync_secrets` does not restart the service by itself.)

### Manual SSH when you need a shell

```bash
ssh USER@PI_HOST
cd ~/jarvis
sudo systemctl status jarvis
sudo journalctl -u jarvis -f
```

---

## Voice / Home Assistant (#28)

Voice bridges and HA should talk to Jarvis on **localhost or LAN**. They do not need a public URL. Wire that integration under #28; this guide only keeps the API supervised and reachable on the home network.

---

## What not to do on the Pi

| Avoid | Why |
|-------|-----|
| `JARVIS_EXPOSE_API_WITH_CLOUDFLARED=1` | Legacy quick tunnel + Firebase/Telegram URL publish; replaced later by #31 / cleaned in #30 |
| Router port-forward of SSH or `:8000` | Exposes the home network; use Tailscale/named tunnel (#31) instead |
| Daily smart-plug power cuts | Unclean shutdowns wear the SD card; leave the Pi on |

---

## Helper reference

See [deploy/README.md](../deploy/README.md) for the file list. Secret group names live in `deploy/secret_paths.py`.
