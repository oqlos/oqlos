"""
oqlos/core/safe_eval.py — Sandboxed expression evaluator for OQL conditions.

Replaces raw eval() with a restricted expression parser.
Only allows comparisons, arithmetic, and whitelisted names.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
}

_ALLOWED_NAMES = {"True": True, "False": False, "None": None}
_ALLOWED_FUNCS = {"abs": abs, "min": min, "max": max, "round": round, "int": int, "float": float}


class SafeEvalError(Exception):
    """Raised when an expression cannot be safely evaluated."""


def safe_eval(expr: str, context: dict[str, Any] | None = None) -> Any:
    """
    Evaluate a simple expression safely without using eval().

    Supports:
      - Numeric literals, strings, booleans, None
      - Comparisons: ==, !=, <, <=, >, >=
      - Arithmetic: +, -, *, /, %
      - Boolean: and, or, not
      - Variable lookup from context dict
      - Whitelisted functions: abs, min, max, round, int, float

    Raises SafeEvalError on disallowed constructs.
    """
    ctx = dict(context or {})
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise SafeEvalError(f"Invalid expression: {e}") from e

    return _eval_node(tree.body, ctx)


def _eval_node(node: ast.AST, ctx: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, ctx)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        name = node.id
        if name in _ALLOWED_NAMES:
            return _ALLOWED_NAMES[name]
        if name in ctx:
            return ctx[name]
        raise SafeEvalError(f"Undefined variable: {name}")

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, ctx)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.Not):
            return not operand
        raise SafeEvalError(f"Unsupported unary op: {type(node.op).__name__}")

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, ctx)
        right = _eval_node(node.right, ctx)
        op_fn = _SAFE_OPS.get(type(node.op))
        if op_fn is None:
            raise SafeEvalError(f"Unsupported operator: {type(node.op).__name__}")
        return op_fn(left, right)

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, ctx)
            op_fn = _SAFE_OPS.get(type(op))
            if op_fn is None:
                raise SafeEvalError(f"Unsupported comparison: {type(op).__name__}")
            if not op_fn(left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, ctx) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_FUNCS:
            args = [_eval_node(a, ctx) for a in node.args]
            return _ALLOWED_FUNCS[node.func.id](*args)
        raise SafeEvalError(f"Function not allowed: {ast.dump(node.func)}")

    if isinstance(node, ast.IfExp):
        test = _eval_node(node.test, ctx)
        return _eval_node(node.body, ctx) if test else _eval_node(node.orelse, ctx)

    raise SafeEvalError(f"Unsupported expression: {type(node).__name__}")
