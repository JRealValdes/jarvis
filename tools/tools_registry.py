import importlib
import pkgutil
import inspect
import os

# Ruta absoluta del directorio actual
current_dir = os.path.dirname(__file__)
package_name = __package__ or "tools"

local_tools = []

for _, module_name, is_pkg in pkgutil.iter_modules([current_dir]):
    if is_pkg or module_name.startswith("_"):
        continue  # Skipping sub-packages and private files

    module = importlib.import_module(f"{package_name}.{module_name}")

    for name, obj in inspect.getmembers(module):
        if name.endswith("_tool"):
            local_tools.append(obj)
