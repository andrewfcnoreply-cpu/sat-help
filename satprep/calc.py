"""
A small, safe scientific calculator for the Math section.

We never use Python's eval() on what you type, because eval() can run any
code. Instead we parse the expression into a tree (with the built-in `ast`
module) and only allow numbers, + - * / ^, parentheses, and a fixed list of
math functions.
"""

from __future__ import annotations

import ast
import math
import operator

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

_CONSTANTS = {"pi": math.pi, "π": math.pi, "e": math.e}


def _functions(degrees: bool) -> dict:
    to_rad = math.radians if degrees else (lambda x: x)
    from_rad = math.degrees if degrees else (lambda x: x)
    return {
        "sqrt": math.sqrt, "abs": abs, "round": round,
        "sin": lambda x: math.sin(to_rad(x)),
        "cos": lambda x: math.cos(to_rad(x)),
        "tan": lambda x: math.tan(to_rad(x)),
        "asin": lambda x: from_rad(math.asin(x)),
        "acos": lambda x: from_rad(math.acos(x)),
        "atan": lambda x: from_rad(math.atan(x)),
        "log": math.log10, "ln": math.log,
    }


def evaluate(expression: str, degrees: bool = True) -> float:
    """Calculate an expression like '2^3 + sqrt(16)'. Raises ValueError if invalid."""
    text = (expression.replace("^", "**").replace("×", "*").replace("÷", "/")
            .replace("−", "-").replace("√", "sqrt"))
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        raise ValueError("Check the expression")
    funcs = _functions(degrees)

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("Exponent too large")
            return _BINARY[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](walk(node.operand))
        if isinstance(node, ast.Name) and node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in funcs and not node.keywords):
            return funcs[node.func.id](*[walk(a) for a in node.args])
        raise ValueError("Not allowed in the calculator")

    try:
        result = walk(tree)
    except (ZeroDivisionError, OverflowError, TypeError) as e:
        raise ValueError(str(e) or "Math error")
    if isinstance(result, complex):
        raise ValueError("No real answer")
    return float(result)


def format_number(value: float) -> str:
    """Show 4.0 as 4 and trim long decimals."""
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.10g}"
