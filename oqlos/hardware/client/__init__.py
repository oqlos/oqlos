"""OqlOS hardware REST client contract."""

from oqlos.hardware.client.adc import adc_sensor_alias, normalize_adc_read_all_result, normalize_adc_read_result
from oqlos.hardware.client.autorepair import (
    analyze_repair_needs,
    build_summary,
    is_stale_hardware_entry,
    is_stale_hardware_message,
    modbus_exclusive_scan_recommended,
    modbus_plugins_need_repair,
    overall_stack_healthy,
    plugin_needs_repair,
)
from oqlos.hardware.client.config import OqlosHardwareProxyConfig, candidate_oqlos_bases, float_from_env
from oqlos.hardware.client.constants import (
    ARTIFICIAL_LUNG_IDS,
    DEFAULT_OQLOS_API_BASE,
    FALLBACK_ADAPTERS,
    MODBUS_ALLOWED_VALVE_IDS,
    OQLOS_HARDWARE_PREFIX,
    PERIPHERAL_STATUS_COMMANDS,
    PERIPHERAL_STATUS_PLUGIN_ALIASES,
    TIC249_DEFAULT_TARGET_VELOCITY,
)
from oqlos.hardware.client.errors import (
    HardwareProxyError,
    diagnostic_issue_for_peripheral,
    is_oqlos_unavailable,
    oqlos_error_detail,
)
from oqlos.hardware.client.identify_enrich import enrich_hardware_identify
from oqlos.hardware.client.modbus_repair import rewrite_modbus_repair
from oqlos.hardware.client.proxy import OqlosHardwareProxy
from oqlos.hardware.client.resolvers import (
    extract_command_failure,
    normalize_modbus_valve_id,
    resolve_artificial_lung_target,
    resolve_diagnostic_target,
    resolve_lung_target,
    resolve_modbus_adc_target,
    resolve_modbus_target,
    resolve_pump_target,
    resolve_rtc_target,
)
from oqlos.hardware.client.tic249_arg_contract import (
    MOTOR2_RUNTIME_ALIASES,
    canonicalize_motor2_runtime_key,
    tic249_runtime_args_from_config,
)
from oqlos.hardware.client.tic249_extended import MOTOR_TIC249_EXTENDED_COMMANDS, run_extended_motor_tic249_command
from oqlos.hardware.client.tic249_rig_direction import (
    PLUGIN_FORWARD,
    PLUGIN_REVERSE,
    apply_rig_direction_to_plugin_params,
    rig_direction_to_plugin,
)

__all__ = [
    "OqlosHardwareProxy",
    "ARTIFICIAL_LUNG_IDS",
    "DEFAULT_OQLOS_API_BASE",
    "FALLBACK_ADAPTERS",
    "HardwareProxyError",
    "MODBUS_ALLOWED_VALVE_IDS",
    "MOTOR2_RUNTIME_ALIASES",
    "OQLOS_HARDWARE_PREFIX",
    "OqlosHardwareProxyConfig",
    "PERIPHERAL_STATUS_COMMANDS",
    "PERIPHERAL_STATUS_PLUGIN_ALIASES",
    "PLUGIN_FORWARD",
    "PLUGIN_REVERSE",
    "TIC249_DEFAULT_TARGET_VELOCITY",
    "MOTOR_TIC249_EXTENDED_COMMANDS",
    "adc_sensor_alias",
    "analyze_repair_needs",
    "apply_rig_direction_to_plugin_params",
    "build_summary",
    "canonicalize_motor2_runtime_key",
    "candidate_oqlos_bases",
    "enrich_hardware_identify",
    "diagnostic_issue_for_peripheral",
    "extract_command_failure",
    "float_from_env",
    "is_oqlos_unavailable",
    "is_stale_hardware_entry",
    "is_stale_hardware_message",
    "normalize_adc_read_all_result",
    "normalize_adc_read_result",
    "normalize_modbus_valve_id",
    "modbus_exclusive_scan_recommended",
    "modbus_plugins_need_repair",
    "oqlos_error_detail",
    "overall_stack_healthy",
    "plugin_needs_repair",
    "resolve_artificial_lung_target",
    "resolve_diagnostic_target",
    "resolve_lung_target",
    "resolve_modbus_adc_target",
    "resolve_modbus_target",
    "resolve_pump_target",
    "resolve_rtc_target",
    "rewrite_modbus_repair",
    "rig_direction_to_plugin",
    "run_extended_motor_tic249_command",
    "tic249_runtime_args_from_config",
]
