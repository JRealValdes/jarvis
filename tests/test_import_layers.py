"""Regression: lower layers must not import the HTTP API package."""

import ast
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Modules that must not depend on ``api`` (avoids tools → api → agents cycles).
_ISOLATED_PREFIXES = ("tools/", "domain/", "infrastructure/", "core/")


def _imports_api(module_path: Path) -> bool:
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "api" or alias.name.startswith("api."):
                    return True
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "api" or node.module.startswith("api."):
                return True
    return False


def test_lower_layers_do_not_import_api():
    offenders: list[str] = []
    for prefix in _ISOLATED_PREFIXES:
        base = _PROJECT_ROOT / prefix.rstrip("/")
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if path.name.startswith("_"):
                continue
            if _imports_api(path):
                offenders.append(str(path.relative_to(_PROJECT_ROOT)))
    assert offenders == [], f"Unexpected api imports: {offenders}"
