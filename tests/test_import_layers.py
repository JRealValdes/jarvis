"""Regression: lower layers must not import the HTTP API package."""

import ast
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_JARVIS_SRC = _PROJECT_ROOT / "src" / "jarvis"

# Modules that must not depend on ``jarvis.api`` (avoids tools → api → agents cycles).
_ISOLATED_PREFIXES = ("tools", "domain", "infrastructure", "core")


def _imports_api(module_path: Path) -> bool:
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("api", "jarvis.api") or alias.name.startswith(
                    ("api.", "jarvis.api.")
                ):
                    return True
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module in ("api", "jarvis.api") or node.module.startswith(
                ("api.", "jarvis.api.")
            ):
                return True
    return False


def test_lower_layers_do_not_import_api():
    offenders: list[str] = []
    for prefix in _ISOLATED_PREFIXES:
        base = _JARVIS_SRC / prefix
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if path.name.startswith("_"):
                continue
            if _imports_api(path):
                offenders.append(str(path.relative_to(_PROJECT_ROOT)))
    assert offenders == [], f"Unexpected api imports: {offenders}"
