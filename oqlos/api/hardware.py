# firmware/api/hardware.py
"""Hardware API facade — composes sub-routers and re-exports legacy symbols."""

from __future__ import annotations

from oqlos.api.hardware_actuators import router as hardware_actuators_router, set_pump, set_valve
from oqlos.api.hardware_diagnosis_routes import (
    hardware_diagnosis_route,
    hardware_recover_route,
    hardware_stack_snapshot,
    router as hardware_diagnosis_router,
)
from oqlos.api.hardware_gateway import get_hardware_gateway as _gw, set_hardware_gateway
from oqlos.api.hardware_hui import (
    hui_actions,
    hui_al_start,
    hui_al_stop,
    hui_hold_start,
    hui_hold_stop,
    hui_shutdown,
    hui_valve_key,
    router as hardware_hui_router,
)
from oqlos.api.hardware_identify import (
    _hardware_health_overall_ok,
    hardware_health,
    hardware_identify,
    router as hardware_identify_router,
)
from oqlos.api.hardware_runtime import (
    hardware_diagnose,
    hardware_temperature,
    read_cpu_temperature as _read_cpu_temperature,
    read_sensor,
    read_sensors_batch,
    router as hardware_runtime_router,
)
from oqlos.api.hardware_registry import HARDWARE_REGISTRY as _HARDWARE_REGISTRY
from oqlos.api.hardware_lung import (
    TIC249_DEFAULT_TARGET_VELOCITY,
    artificial_lung_command,
    artificial_lung_status,
    command_payload as _command_payload,
    disable_lung,
    router as hardware_lung_router,
    set_lung,
    stop_lung,
)
from oqlos.api.hardware_modbus_routes import router as hardware_modbus_router
from oqlos.api.hardware_peripherals_routes import (
    read_modbus_adc_raw,
    router as hardware_peripherals_router,
    rtc_command,
    rtc_status,
)
from oqlos.api.hardware_modbus_topology import _modbus_io_device_ids, _modbus_runtime_serial_ports
from oqlos.api.hardware_modbus_waveshare import (
    _build_waveshare_diagnose_report,
    _diagnose_shared_bus_matrix,
    _modbus_health_serial_stale,
)
from oqlos.api.hardware_modbus_wizard import (
    _modbus_wizard_plan,
    _modbus_wizard_program_isolated,
)
from oqlos.api.hardware_platform import _detect_runtime_platform
from oqlos.api.hardware_probe import (
    _collect_hardware_diagnostics,
    _modbus_health_is_no_response,
    _probe_all_hardware,
    _probe_selected_hardware,
    _scan_usb_devices,
)
from fastapi import APIRouter

from oqlos.hardware.rtc_probe import build_rtc_peripheral_status, run_rtc_command

router = APIRouter(prefix="/api/v1/hardware", tags=["hardware"])
router.include_router(hardware_identify_router)
router.include_router(hardware_hui_router)
router.include_router(hardware_runtime_router)
router.include_router(hardware_actuators_router)
router.include_router(hardware_lung_router)
router.include_router(hardware_modbus_router)
router.include_router(hardware_diagnosis_router)
router.include_router(hardware_peripherals_router)
