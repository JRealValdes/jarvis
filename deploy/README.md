# Deploy helpers (Raspberry Pi)

Operator tooling for [issue #29](https://github.com/JRealValdes/jarvis/issues/29): push secrets and update code on a headless Pi over SSH.

**Full guide:** [docs/raspberry-pi-ops.md](../docs/raspberry-pi-ops.md)

| File | Purpose |
|------|---------|
| `pi.env.example` | Copy to `pi.local.env` (gitignored) with host/user/path |
| `sync_secrets.py` | Copy local secrets to the Pi (`scp`) |
| `update_code.py` | `git pull` + `uv sync` + restart `jarvis.service` on the Pi |
| `jarvis.service` | systemd unit template for `uv run jarvis api` |
| `secret_paths.py` | Catalog of secret path groups for `--only` |

```bash
cp deploy/pi.env.example deploy/pi.local.env   # then edit
uv run python deploy/sync_secrets.py --dry-run
uv run python deploy/update_code.py --dry-run
```
