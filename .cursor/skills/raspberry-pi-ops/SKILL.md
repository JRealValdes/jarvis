---
name: raspberry-pi-ops
description: >-
  Update or sync Jarvis on the LAN Raspberry Pi (Jarvis Server): stop service,
  git pull, uv sync, restart, health-check; or push secrets via scp. Use when
  the user asks to update the raspberry, update the server, update Jarvis
  Server, deploy/push code to the Pi, sync/push secrets to the Pi, or similar
  phrases in any language.
---

# Raspberry Pi / Jarvis Server ops

Operator PC → headless Pi on the LAN. Full human guide: `docs/raspberry-pi-ops.md`.

Config (gitignored): `deploy/pi.local.env` from `deploy/pi.env.example`
(`JARVIS_PI_USER`, `JARVIS_PI_HOST`, `JARVIS_PI_DIR`).

## Preconditions

1. Read `deploy/pi.local.env` exists (do not print secret file contents from the Pi).
2. Prefer **SSH key** auth. Scripts default to `BatchMode=yes` (no password prompts).
3. Passwordless `sudo` for `systemctl` on `jarvis.service` is required for unattended restart (see docs).
4. If key/sudo missing, tell the user to finish that setup; only use `--allow-password` if they explicitly agree to interactive prompts.

## Phrase → action

| User intent (examples) | Action |
|------------------------|--------|
| update raspberry / update server / update Jarvis Server / lleva esto a la Pi | **Code update** |
| update/sync/push secrets / lleva los secretos | **Secrets sync** |
| both | Secrets first (with `--restart`), or code update then secrets — ask only if unclear |

### Code update

From repo root on the operator PC:

```bash
uv run python deploy/update_code.py --dry-run
uv run python deploy/update_code.py
```

Remote flow: stop `jarvis` → `git pull --ff-only` → `uv sync` → start → health-check `http://127.0.0.1:8000/docs`. On pull/sync failure the script tries to start the service again.

Report success/failure from the command output. On failure, suggest `ssh … 'systemctl status jarvis'` / `journalctl -u jarvis -n 50`.

### Secrets sync

```bash
uv run python deploy/sync_secrets.py --dry-run
uv run python deploy/sync_secrets.py --restart
```

`--restart` reloads the API so new `.env` values apply. Use `--only group1,group2` only when the user asks for a subset (`--list-groups`).

### New secret files in the repo

If this change (or the user) introduces a new Pi-bound secret path, update `deploy/secret_paths.py` in the same work. See rule `pi-secrets-catalog` and the module docstring.

## Do not

- Commit `deploy/pi.local.env` or secret files
- Port-forward SSH or `:8000` on the router (off-LAN is #31 / Tailscale)
