"""Automatic discovery of LangChain tools in ``jarvis.tools.builtins``."""

import importlib
import inspect
import pkgutil
from pathlib import Path

_BUILTINS_DIR = Path(__file__).resolve().parent / "builtins"
_BUILTINS_PACKAGE = "jarvis.tools.builtins"

local_tools: list = []
"""List of @tool objects registered when this module is imported."""

for _, module_name, is_pkg in pkgutil.iter_modules([str(_BUILTINS_DIR)]):
    if is_pkg or module_name.startswith("_"):
        continue

    module = importlib.import_module(f"{_BUILTINS_PACKAGE}.{module_name}")

    for name, obj in inspect.getmembers(module):
        if name.endswith("_tool"):
            local_tools.append(obj)
