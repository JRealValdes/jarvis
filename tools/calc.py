from langchain_core.tools import tool

@tool
def calculate(expression: str) -> str:
    """Evaluate a math expression in Python."""
    try:
        print(f"I'm entering calculate tool, sir. Expression under evaluation: {expression}.")
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"
