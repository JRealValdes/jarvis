import json
import os
from typing import List
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Math")

@mcp.tool()
def add(a: int, b: int) -> int:
    """
    Add two integers.
    
    Args:
        a: First integer
        b: Second integer
    Returns:
        Sum of a and b
    """
    return a + b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """
    Multiply two integers.

    Args:
        a: First integer
        b: Second integer
    Returns:
        Product of a and b
    """
    return a * b

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
