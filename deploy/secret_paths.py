"""Catalog of local secret / runtime paths to push to a headless Pi.

Paths are relative to the repository root. Groups map to ``--only`` names.

**Keeping this catalog current (required):** whenever you add a new secret or
machine-local runtime file that must live on the Pi (new ``.env``-adjacent
file, credential JSON, per-user YAML, DB, etc.), update ``SECRET_GROUPS`` or
``SECRET_GLOBS`` here in the same change. Also mention the path in
``README.md`` (Local runtime assets) when it is operator-facing. The Cursor
skill ``raspberry-pi-ops`` and rule ``pi-secrets-catalog`` remind agents to do
this — do not rely on memory alone.
"""

from __future__ import annotations

from pathlib import Path

# Named groups for ``sync_secrets.py --only``. Default = all groups that have
# at least one existing local file (example_* templates are skipped).
SECRET_GROUPS: dict[str, tuple[str, ...]] = {
    "env": (".env",),
    "users-db": ("data/users.db",),
    "firebase": ("data/firebase_project_secret_private_key.json",),
    "mcp": ("data/mcp/server_config.json",),
}

# Globs expanded under the project root; example_user / example_* paths skipped.
SECRET_GLOBS: dict[str, tuple[str, ...]] = {
    "user-prefs": (
        "data/users/*/job_preferences.yaml",
        "data/users/*/linkedin_reply_examples.yaml",
    ),
    "google": (
        "data/google/*/*/*secret*.json",
        "data/google/*/*/token.json",
        "data/google/*/*/*token*.json",
    ),
}

_SKIP_NAME_MARKERS: tuple[str, ...] = ("example_user", "example_account", "example_")


def list_group_names() -> list[str]:
    """Return sorted secret group names available for ``--only``."""
    return sorted({*SECRET_GROUPS, *SECRET_GLOBS})


def _is_example_path(path: Path) -> bool:
    """Return True if the path looks like a tracked example template."""
    parts = path.parts
    name = path.name
    if "example_user" in parts or "example_account" in parts:
        return True
    if name.startswith("example_") or name.endswith("_example.json"):
        return True
    for marker in _SKIP_NAME_MARKERS:
        if marker in name and "example" in name:
            return True
    return False


def resolve_secret_paths(
    project_root: Path,
    only: list[str] | None = None,
) -> list[Path]:
    """
    Resolve existing local secret paths under ``project_root``.

    Args:
        project_root: Repository root (contains ``pyproject.toml``).
        only: Optional group names; ``None`` or empty means all groups.

    Returns:
        Sorted unique absolute paths that exist on disk (examples excluded).

    Raises:
        ValueError: If an unknown group name is requested.
    """
    root = project_root.resolve()
    known = set(list_group_names())
    selected = list(only) if only else list_group_names()
    unknown = sorted(set(selected) - known)
    if unknown:
        raise ValueError(
            f"Unknown secret group(s): {', '.join(unknown)}. "
            f"Known: {', '.join(sorted(known))}"
        )

    found: set[Path] = set()
    for group in selected:
        for rel in SECRET_GROUPS.get(group, ()):
            path = root / rel
            if path.is_file() and not _is_example_path(path):
                found.add(path)
        for pattern in SECRET_GLOBS.get(group, ()):
            for path in root.glob(pattern):
                if path.is_file() and not _is_example_path(path):
                    found.add(path)

    return sorted(found)


def relative_to_root(path: Path, project_root: Path) -> Path:
    """Return ``path`` relative to ``project_root``."""
    return path.resolve().relative_to(project_root.resolve())
