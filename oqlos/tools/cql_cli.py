"""
CQL CLI entry point — run, validate, and batch-check .cql/.oql scenario files.

This module is now a thin backward-compatible wrapper around the cql_cli package.
The implementation has been modularized into:
  - oqlos.tools.cql_cli.main: Entry point and argument parsing
  - oqlos.tools.cql_cli.preflight: Hardware preflight checks
  - oqlos.tools.cql_cli.commands: Command execution helpers
  - oqlos.tools.cql_cli.utils: Utility functions

Usage:
  oqlctl file.cql
  oqlctl file.cql --mode validate
  oqlctl --validate-dir scenarios/
  oqlctl cmd "SET 'pompa 1' '0'"
  python -m oqlos.tools.cql_cli file.oql --mode dry-run
"""

# Re-export for backward compatibility
from oqlos.tools.cql_cli.main import main
from oqlos.tools.cql_cli.utils import (
    output_yaml as _output_yaml,
    parse_sensor_overrides as _parse_sensor_overrides,
    build_result_payload as _result_payload,
    normalize_target_name as _normalize_target_name,
    resolve_required_adapter as _resolve_required_adapter,
    build_single_command_scenario as _build_single_command_scenario,
    validate_directory as _validate_directory,
)
from oqlos.tools.cql_cli.preflight import (
    ensure_firmware_running as _ensure_firmware_running,
    preflight_hardware as _preflight_hardware,
)
from oqlos.tools.cql_cli.commands import (
    run_source as _run_source,
    run_single_command as _run_single_command,
    DEFAULT_FIRMWARE_URL,
)

__all__ = ["main"]

# Backward compatibility aliases
_output_yaml = _output_yaml
_parse_sensor_overrides = _parse_sensor_overrides
_result_payload = _result_payload
_normalize_target_name = _normalize_target_name
_resolve_required_adapter = _resolve_required_adapter
_preflight_hardware = _preflight_hardware
_build_single_command_scenario = _build_single_command_scenario
_run_source = _run_source
_run_single_command = _run_single_command
_validate_directory = _validate_directory
_ensure_firmware_running = _ensure_firmware_running


if __name__ == "__main__":
    main()
