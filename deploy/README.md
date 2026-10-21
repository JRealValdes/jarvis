# Deploy helpers (Raspberry Pi)

Operator tooling for [issue #29](https://github.com/JRealValdes/jarvis/issues/29): push secrets and update code on a headless Pi over SSH.

**Full guide:** [docs/raspberry-pi-ops.md](../docs/raspberry-pi-ops.md)  
**Cursor skill:** `.cursor/skills/raspberry-pi-ops/` (phrases like “update the raspberry”, “sync secrets”)

| File | Purpose |
|------|---------|
| `pi.env.example` | Copy to `pi.local.env` (gitignored) with host/user/path |
| `pi_env.py` | Shared loader for `JARVIS_PI_*` + SSH helpers |
| `sync_secrets.py` | Copy local secrets to the Pi (`scp`); optional `--restart` |
| `update_code.py` | Stop → `git pull` → `uv sync` → start → health-check |
| `jarvis.service` | systemd unit template for `uv run jarvis api` |
| `secret_paths.py` | Catalog of secret path groups for `--only` (**keep updated**) |

```bash
cp deploy/pi.env.example deploy/pi.local.env   # then edit
uv run python deploy/sync_secrets.py --dry-run
uv run python deploy/sync_secrets.py --restart
uv run python deploy/update_code.py --dry-run
uv run python deploy/update_code.py
```

Defaults use SSH **BatchMode** (key auth). Pass `--allow-password` only for interactive fallback.
