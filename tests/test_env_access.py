"""Regression: only jarvis.core.config loads dotenv and reads the environment."""

from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "jarvis"
_MARKERS = ("os.getenv", "os.environ", "load_dotenv")


def test_environment_is_read_only_from_config():
    offenders: list[str] = []
    for path in _SRC.rglob("*.py"):
        if path.name == "config.py" and path.parent.name == "core":
            continue
        text = path.read_text(encoding="utf-8")
        for marker in _MARKERS:
            if marker in text:
                relative = path.relative_to(_SRC.parents[1])
                offenders.append(f"{relative.as_posix()}:{marker}")
    assert offenders == []
