"""Canonical public entry point for the OQL command-line interface.

The implementation package keeps its historical path temporarily for import
compatibility. New runtime integrations import exclusively from this module.
"""

from __future__ import annotations

from oqlos.tools.cql_cli import main


def run_single_command(*args, **kwargs):
    """Execute one OQL command through the current runtime implementation."""
    from oqlos.tools.cql_cli import commands

    return commands.run_single_command(*args, **kwargs)


def run_source(*args, **kwargs):
    """Execute OQL source through the current runtime implementation."""
    from oqlos.tools.cql_cli import commands

    return commands.run_source(*args, **kwargs)


def build_result_payload(*args, **kwargs):
    """Build the stable public result payload for an OQL execution."""
    from oqlos.tools.cql_cli import utils

    return utils.build_result_payload(*args, **kwargs)

__all__ = ["build_result_payload", "main", "run_single_command", "run_source"]


if __name__ == "__main__":
    main()
