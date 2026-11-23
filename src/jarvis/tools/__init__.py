"""Jarvis tools package.

Import tools from submodules (``jarvis.tools.registry``, ``jarvis.tools.errors``,
``jarvis.tools.builtins``) rather than this package root. Keeping the package
``__init__`` free of the registry avoids import cycles when graph/seed code
loads ``jarvis.tools.errors`` while a builtin still imports infrastructure.
"""

__all__: list[str] = []
