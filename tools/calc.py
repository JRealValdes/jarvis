"""Safe arithmetic calculator tool for the agent."""

import ast

from langchain_core.tools import tool


@tool
def calculate_tool(expression: str) -> float | int:
    """
    Evalúa una expresión matemática de forma restringida (solo literales y operadores).

    Args:
        expression: Expresión Python válida en modo eval (ej. ``2 + 2 * 3``).

    Returns:
        Resultado numérico; floats redondeados a 2 decimales.

    Raises:
        ValueError: Si la expresión no es válida o la evaluación falla.
    """
    try:
        node = ast.parse(expression, mode="eval")
        code = compile(node, "<string>", "eval")
        result = eval(code, {"__builtins__": {}})
        return round(result, 2) if isinstance(result, float) else result
    except Exception as e:
        raise ValueError(f"Error while evaluating expression: {e}") from e
