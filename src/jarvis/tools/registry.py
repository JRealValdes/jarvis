"""Explicit registry of LangChain tools shipped with Jarvis."""

from jarvis.tools.builtins import BUILTIN_TOOLS

local_tools: list = list(BUILTIN_TOOLS)
"""Tools bound to agents. Edit ``jarvis.tools.builtins.BUILTIN_TOOLS`` to change it."""
