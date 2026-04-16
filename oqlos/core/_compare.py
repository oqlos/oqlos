"""Shared comparison operators used by executor.py and safe_eval.py.

Extracted from duplication group [4c4831cb00e059bf].
"""

import ast
import operator
from collections.abc import Callable
from typing import Any

COMPARE_OPS: dict[type, Any] = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


def resolve_compare(left: Any, op: ast.cmpop, right: Any) -> bool:
    """Evaluate a single comparison: left op right."""
    fn = COMPARE_OPS.get(type(op))
    if fn is None:
        raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")
    return fn(left, right)


def resolve_compare_chain(
    node: ast.Compare,
    resolve_value: Callable[[ast.AST], Any],
) -> bool:
    """Evaluate a chained comparison using the caller's node resolver."""
    left = resolve_value(node.left)
    for op, comparator in zip(node.ops, node.comparators):
        right = resolve_value(comparator)
        if not resolve_compare(left, op, right):
            return False
        left = right
    return True
