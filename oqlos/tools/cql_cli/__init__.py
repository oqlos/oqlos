"""Backward-compatible module path for the modular OQL CLI."""

from __future__ import annotations

from oqlos.core.interpreter import CqlInterpreter
from oqlos.tools.hardware_diagnose.health import check_firmware_health, check_firmware_identify

from . import commands as _commands_module
from . import main as _main_module
from . import preflight as _preflight_module
from .commands import (
  DEFAULT_FIRMWARE_URL,
  default_firmware_url,
  run_single_command as _run_single_command,
  run_source as _run_source,
)
from .preflight import ensure_firmware_running as _ensure_firmware_running, preflight_hardware as _preflight_hardware
from .utils import (
  build_result_payload as _result_payload,
  build_single_command_scenario as _build_single_command_scenario,
  normalize_target_name as _normalize_target_name,
  output_yaml as _output_yaml,
  parse_sensor_overrides as _parse_sensor_overrides,
  resolve_required_adapter as _resolve_required_adapter,
  validate_directory as _validate_directory,
)


def _sync_compat_symbols() -> None:
  _preflight_module.check_firmware_health = check_firmware_health
  _preflight_module.check_firmware_identify = check_firmware_identify
  _preflight_module.ensure_firmware_running = _ensure_firmware_running

  _commands_module.CqlInterpreter = CqlInterpreter
  _commands_module.check_firmware_identify = check_firmware_identify

  _main_module.CqlInterpreter = CqlInterpreter
  _main_module.run_single_command = _run_single_command
  _main_module.preflight_hardware = _preflight_hardware
  _main_module.validate_directory = _validate_directory


def main() -> None:
  _sync_compat_symbols()
  _main_module.main()


__all__ = [
  "main",
  "CqlInterpreter",
  "DEFAULT_FIRMWARE_URL",
  "default_firmware_url",
  "check_firmware_health",
  "check_firmware_identify",
  "_build_single_command_scenario",
  "_ensure_firmware_running",
  "_normalize_target_name",
  "_output_yaml",
  "_parse_sensor_overrides",
  "_preflight_hardware",
  "_resolve_required_adapter",
  "_result_payload",
  "_run_single_command",
  "_run_source",
  "_validate_directory",
]
