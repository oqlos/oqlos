"""Canonical public entry point for the OQL command-line interface.

The implementation remains in ``oqlos.tools.cql_cli`` temporarily so existing
installations keep working. New callers must import or execute this module.
"""

from __future__ import annotations

from oqlos.tools.cql_cli import main

__all__ = ["main"]


if __name__ == "__main__":
    main()
