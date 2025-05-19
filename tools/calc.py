import ast
from langchain_core.tools import tool

@tool
def calculate(expression):
    """
    Evaluate a math expression in Python. Only use if situation requires to solve a math expression.

    Parameters
    ----------
    expression : str
        The mathematical expression as a string to be evaluated.

    Returns
    -------
    result : float or int
        The result of the given mathematical expression.

    Raises
    ------
    ValueError
        If an error occurs while evaluating the expression, such as division by zero or undefined function.
    """
    try:
        parsed_expression = ast.parse(expression, mode='eval')
        result = ast.NodeVisitor(lambda node: ast.literal_eval(ast.unparse(node)), parsed_expression).visit(parsed_expression)
        if isinstance(result, float):
            return round(result, 2)  # Return rounded to two decimal places
        elif isinstance(result, int):
            return result
    except (SyntaxError, NameError, ValueError) as e:
        raise ValueError(f"Error while evaluating expression: {e}")
