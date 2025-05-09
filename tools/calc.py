from langchain.tools import tool

@tool
def calculate(expression: str) -> str:
    """Evalúa una expresión matemática en Python."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"
