"""
CQL CLI package - Modular command-line interface for OQL/CQL.

This package provides a backward-compatible entry point to the CQL CLI functionality.
The implementation has been split into modules for better maintainability:
  - main: Entry point and argument parsing
  - preflight: Hardware preflight checks
  - commands: Command execution helpers
  - utils: Utility functions
"""

from oqlos.tools.cql_cli.main import main

__all__ = ["main"]
