"""
oqlos/core/safe_eval.py — Sandboxed expression evaluator for OQL conditions.

Replaces raw eval() with a restricted expression parser.
Only allows comparisons, arithmetic, and whitelisted names.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

from oqlos.core._compare import resolve_compare

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
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


def _eval_constant(node: ast.Constant, ctx: dict[str, Any]) -> Any:
    """Evaluate a constant literal."""
    return node.value


def _eval_name(node: ast.Name, ctx: dict[str, Any]) -> Any:
    """Evaluate a name lookup (variable or constant)."""
    name = node.id
    if name in _ALLOWED_NAMES:
        return _ALLOWED_NAMES[name]
    if name in ctx:
        return ctx[name]
    raise SafeEvalError(f"Undefined variable: {name}")


def _eval_unary_op(node: ast.UnaryOp, ctx: dict[str, Any]) -> Any:
    """Evaluate a unary operation (-x, not x)."""
    operand = _eval_node(node.operand, ctx)
    if isinstance(node.op, ast.USub):
        return -operand
    if isinstance(node.op, ast.Not):
        return not operand
    raise SafeEvalError(f"Unsupported unary op: {type(node.op).__name__}")


def _eval_bin_op(node: ast.BinOp, ctx: dict[str, Any]) -> Any:
    """Evaluate a binary operation (+, -, *, /, %)."""
    left = _eval_node(node.left, ctx)
    right = _eval_node(node.right, ctx)
    op_fn = _SAFE_OPS.get(type(node.op))
    if op_fn is None:
        raise SafeEvalError(f"Unsupported operator: {type(node.op).__name__}")
    return op_fn(left, right)


def _eval_compare(node: ast.Compare, ctx: dict[str, Any]) -> Any:
    """Evaluate a comparison chain (x < y < z)."""
    left = _eval_node(node.left, ctx)
    for op, comparator in zip(node.ops, node.comparators):
        right = _eval_node(comparator, ctx)
        if not resolve_compare(left, op, right):
            return False
        left = right
    return True


def _eval_bool_op(node: ast.BoolOp, ctx: dict[str, Any]) -> Any:
    """Evaluate a boolean operation (and, or)."""
    values = [_eval_node(v, ctx) for v in node.values]
    if isinstance(node.op, ast.And):
        return all(values)
    if isinstance(node.op, ast.Or):
        return any(values)
    raise SafeEvalError(f"Unsupported bool op: {type(node.op).__name__}")


def _eval_call(node: ast.Call, ctx: dict[str, Any]) -> Any:
    """Evaluate a function call (whitelisted functions only)."""
    if isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_FUNCS:
        args = [_eval_node(a, ctx) for a in node.args]
        return _ALLOWED_FUNCS[node.func.id](*args)
    raise SafeEvalError(f"Function not allowed: {ast.dump(node.func)}")


def _eval_if_exp(node: ast.IfExp, ctx: dict[str, Any]) -> Any:
    """Evaluate a conditional expression (x if test else y)."""
    test = _eval_node(node.test, ctx)
    return _eval_node(node.body, ctx) if test else _eval_node(node.orelse, ctx)


# Registry mapping AST node types to their evaluators
_NODE_EVALUATORS: dict[type[ast.AST], Any] = {
    ast.Expression: lambda node, ctx: _eval_node(node.body, ctx),
    ast.Constant: _eval_constant,
    ast.Name: _eval_name,
    ast.UnaryOp: _eval_unary_op,
    ast.BinOp: _eval_bin_op,
    ast.Compare: _eval_compare,
    ast.BoolOp: _eval_bool_op,
    ast.Call: _eval_call,
    ast.IfExp: _eval_if_exp,
}


def _eval_node(node: ast.AST, ctx: dict[str, Any]) -> Any:
    """Dispatch node evaluation to the appropriate handler."""
    handler = _NODE_EVALUATORS.get(type(node))
    if handler is None:
        raise SafeEvalError(f"Unsupported expression: {type(node).__name__}")
    return handler(node, ctx)
