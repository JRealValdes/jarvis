---
name: raspberry-pi-ops
description: >-
  Update or sync Jarvis on the LAN Raspberry Pi (Jarvis Server): stop service,
  git pull, uv sync, restart, health-check; or push/pull secrets via scp with
  conflict abort. Use when the user asks to update the raspberry, update the
  server, update Jarvis Server, deploy/push code to the Pi, sync/push/pull/
  retrieve secrets to/from the Pi, or similar phrases in any language.
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
| update raspberry / update server / update Jarvis Server / lleva esto a la Pi | **Code update** (+ secrets dry-run check; see below) |
| update/sync/push secrets / lleva los secretos | **Secrets push** |
| pull/retrieve/trae secretos / from the Pi / from the server | **Secrets pull** |
| both code + secrets | Secrets first (with `--restart` on push), or code then secrets — ask only if unclear |

### Code update

From repo root on the operator PC:

```bash
uv run python deploy/update_code.py --dry-run
uv run python deploy/update_code.py
```

Remote flow: stop `jarvis` → `git pull --ff-only` → `uv sync` → start → health-check `http://127.0.0.1:8000/docs`. On pull/sync failure the script tries to start the service again.

Report success/failure from the command output. On failure, suggest `ssh … 'systemctl status jarvis'` / `journalctl -u jarvis -n 50`.

#### Secrets check (always with code update)

After a code-update request (before or after the code deploy; prefer **before** restart-heavy work so the user can decide early), check whether a secrets push is also warranted:

```bash
uv run python deploy/sync_secrets.py --dry-run
```

Interpret the dry-run:

- **No sync needed** — output is effectively idle (`Nothing to transfer.` and/or only `skip` lines, exit 0, no planned `push`/`pull`, no blocked paths). Tell the user that a secrets sync is **not** needed; do not run a real secrets sync unless they ask.
- **Sync may be needed** — dry-run shows planned transfers (`Transferring N file(s)` / `push`/`pull` lines) **or** blocked conflicts. **Ask** the user whether they also want a secrets sync; do **not** push/pull secrets until they confirm. If they say yes, follow **Secrets push** (or conflict rules) below.

Do not treat “code update” alone as permission to sync secrets.

### Secrets push (PC → Pi)

```bash
uv run python deploy/sync_secrets.py --dry-run
uv run python deploy/sync_secrets.py --restart
```

`--restart` reloads the API so new `.env` values apply. Use `--only group1,group2` only when the user asks for a subset (`--list-groups`).

### Secrets pull (Pi → PC)

```bash
uv run python deploy/sync_secrets.py --pull --only user-prefs --dry-run
uv run python deploy/sync_secrets.py --pull --only user-prefs
```

Prefer `--only` for pulls (especially `user-prefs`) so credentials are not overwritten by accident.

### Conflicts

Sync compares local hash, remote hash, and `deploy/.secrets_sync_state.json`.

- If the script **aborts** with blocked paths: report them to the user, including local/remote mtimes and the newer-mtime hint. Do **not** auto-merge, do **not** treat mtime as auto-resolve, and do not pass `--force-*` unless the user explicitly chooses a side.
- `--force-local` → local wins (push that content).
- `--force-remote` → remote wins (pull that content).
- Optional agent-assisted merge of YAML prefs only if the user asks; never auto-merge `.env` / Google secrets.

### New secret files in the repo

If this change (or the user) introduces a new Pi-bound secret path, update `deploy/secret_paths.py` in the same work (include `GROUP_POLICY`). See rule `pi-secrets-catalog` and the module docstring.

## Do not

- Commit `deploy/pi.local.env`, `deploy/.secrets_sync_state.json`, or secret files
- Port-forward SSH or `:8000` on the router (off-LAN: Tailscale per `docs/raspberry-pi-ops.md` / #31)
- Silently overwrite the other side on conflict
