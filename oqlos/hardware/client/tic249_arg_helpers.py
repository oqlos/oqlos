from __future__ import annotations

from typing import Any


def tic249_arg(args: dict[str, Any], snake: str, camel: str | None = None, default: Any = None) -> Any:
    if snake in args:
        return args[snake]
    if camel and camel in args:
        return args[camel]
    return default
