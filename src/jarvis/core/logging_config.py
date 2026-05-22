"""Central logging configuration for Jarvis runtimes."""

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure root logging once (idempotent for repeated calls).

    Args:
        level: Minimum log level for the default handler.

    Returns:
        None.
    """
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
