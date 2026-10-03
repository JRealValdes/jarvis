"""Safe arithmetic calculator tool for the agent."""

import ast

from langchain_core.tools import tool


@tool
def calculate_tool(expression: str) -> float | int:
    """
    Evaluate a math expression in a restricted way (literals and operators only).

    Args:
        expression: Valid Python expression in eval mode (e.g. ``2 + 2 * 3``).

    Returns:
        Numeric result; floats rounded to 2 decimal places.

    Raises:
        ValueError: If the expression is invalid or evaluation fails.
    """
    try:
        node = ast.parse(expression, mode="eval")
        code = compile(node, "<string>", "eval")
        result = eval(code, {"__builtins__": {}})
        return round(result, 2) if isinstance(result, float) else result
    except Exception as e:
        raise ValueError(f"Error while evaluating expression: {e}") from e
