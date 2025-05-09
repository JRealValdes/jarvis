def calculate(expression: str) -> str:
    """Evalúa una expresión matemática en Python."""
    try:
        print(f"I'm entering calculate tool, sir. Expression under evaluation: {expression}.")
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"
