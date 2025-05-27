import ast
from langchain_core.tools import tool

@tool
def calculate_tool(expression: str) -> float:
    """
    Evaluate a math expression in Python securely.
    """
    try:
        node = ast.parse(expression, mode='eval')
        code = compile(node, "<string>", "eval")
        result = eval(code, {"__builtins__": {}})
        return round(result, 2) if isinstance(result, float) else result
    except Exception as e:
        raise ValueError(f"Error while evaluating expression: {e}")
