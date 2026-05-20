"""Descubrimiento automático de herramientas LangChain en el paquete tools."""

import importlib
import inspect
import os
import pkgutil

current_dir = os.path.dirname(__file__)
package_name = __package__ or "tools"

local_tools: list = []
"""Lista de objetos @tool registrados al importar este módulo."""

for _, module_name, is_pkg in pkgutil.iter_modules([current_dir]):
    if is_pkg or module_name.startswith("_"):
        continue

    module = importlib.import_module(f"{package_name}.{module_name}")

    for name, obj in inspect.getmembers(module):
        if name.endswith("_tool"):
            local_tools.append(obj)
