"""Compatibility projection of the shared OQL hardware mapping policy.

The canonical implementation lives in the ``backend-shared-py`` submodule so
BoardNet/OqlOS and DisplayNet use exactly the same persona and section rules.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CANONICAL = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "backend-shared-py"
    / "src"
    / "shared"
    / "hardware_mapping_access.py"
)

if not _CANONICAL.is_file():  # pragma: no cover - uninitialized submodule
    raise ImportError(
        f"Missing canonical hardware mapping policy ({_CANONICAL}). "
        "Run: git submodule update --init packages/backend-shared-py"
    )

_spec = importlib.util.spec_from_file_location(
    "oqlos.api._hardware_mapping_access_impl",
    _CANONICAL,
)
if _spec is None or _spec.loader is None:  # pragma: no cover - invalid checkout
    raise ImportError(f"Cannot load canonical hardware mapping policy: {_CANONICAL}")
_impl = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _impl
_spec.loader.exec_module(_impl)

__all__ = list(_impl.__all__)
globals().update({name: getattr(_impl, name) for name in __all__})
