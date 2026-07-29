"""Live Modbus channel snapshots and register writes for the hardware-modbus UI."""

from __future__ import annotations

from typing import Any

from oqlos.api.hardware_gateway import get_hardware_gateway, is_plugin_compatible
from oqlos.api.hardware_modbus_settings import MODBUS_PROFILE_IDS, read_modbus_baud_settings
from oqlos.config import get_settings
from oqlos.errors import OqlosError
from oqlos.hardware.power_safety import ensure_power_safe

_settings = get_settings()

IO_MODE_BASE = 0x1000
UART_REGISTER = 0x2000
DEVICE_ADDRESS_REGISTER = 0x4000


def _config_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    uart = data.get("uart_register") or {}
    return [
        {
            "id": "SLAVE_ADDR",
            "label": "Slave address",
            "kind": "config",
            "register_type": "holding",
            "address": DEVICE_ADDRESS_REGISTER,
            "address_hex": hex(DEVICE_ADDRESS_REGISTER),
            "value": data.get("device_id_register"),
            "writable": True,
            "write": {"type": "holding_register", "address": DEVICE_ADDRESS_REGISTER},
        },
        {
            "id": "UART_CFG",
            "label": "UART config",
            "kind": "config",
            "register_type": "holding",
            "address": UART_REGISTER,
            "address_hex": hex(UART_REGISTER),
            "value": data.get("uart_register_raw"),
            "value_decoded": uart,
            "writable": True,
            "write": {"type": "holding_register", "address": UART_REGISTER},
        },
    ]


def _io_channel_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, value in enumerate(data.get("coils") or []):
        rows.append(
            {
                "id": f"DO{idx + 1}",
                "label": f"DO{idx + 1}",
                "kind": "digital_output",
                "register_type": "coil",
                "address": idx,
                "address_hex": f"coil:{idx}",
                "value": value,
                "writable": True,
                "write": {"type": "coil", "address": idx},
            }
        )
    for idx, value in enumerate(data.get("discrete_inputs") or []):
        rows.append(
            {
                "id": f"DI{idx + 1}",
                "label": f"DI{idx + 1}",
                "kind": "digital_input",
                "register_type": "discrete_input",
                "address": idx,
                "address_hex": f"di:{idx}",
                "value": value,
                "writable": False,
            }
        )
    for idx, value in enumerate(data.get("output_mode_registers") or []):
        address = IO_MODE_BASE + idx
        rows.append(
            {
                "id": f"OUT_MODE_{idx + 1}",
                "label": f"Output mode CH{idx + 1}",
                "kind": "output_mode",
                "register_type": "holding",
                "address": address,
                "address_hex": hex(address),
                "value": value,
                "writable": True,
                "write": {"type": "holding_register", "address": address},
            }
        )
    return rows


def _adc_channel_rows(data: dict[str, Any], read_address: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    channels = data.get("channels") or {}
    registers = data.get("registers") or []
    for idx, raw in enumerate(registers[:8]):
        key = f"ai{idx + 1:02d}"
        formatted = channels.get(key) or {}
        rows.append(
            {
                "id": f"AI{idx + 1}",
                "label": f"AI{idx + 1}",
                "kind": "analog_input",
                "register_type": "input",
                "address": read_address + idx,
                "address_hex": hex(read_address + idx),
                "value": raw,
                "value_scaled": formatted.get("value"),
                "unit": formatted.get("unit"),
                "writable": False,
            }
        )
    return rows


def _role_device_id(role: str) -> int:
    if role == "modbus-adc":
        return int(getattr(_settings, "modbus_adc_device_id", 1) or 1)
    return int(getattr(_settings, "modbus_device_id", 1) or 1)


async def _read_module_channels(role: str, profile_cfg: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    device_id = _role_device_id(role)
    entry = health.get(role) or {}
    if not is_plugin_compatible(entry):
        return {
            "module_role": role,
            "ok": False,
            "device_id": device_id,
            "serial_port": profile_cfg.get("serial_port") if role != "modbus-adc" else None,
            "message": str(entry.get("message") or "Plugin not connected"),
            "config_registers": [],
            "channels": [],
        }

    gateway = get_hardware_gateway()
    plugin = await gateway._get_or_connect_plugin(role)
    if plugin is None:
        return {
            "module_role": role,
            "ok": False,
            "device_id": device_id,
            "message": f"{role} plugin unavailable",
            "config_registers": [],
            "channels": [],
        }

    params = plugin.config.connection_params if hasattr(plugin, "config") else {}
    serial_port = str(params.get("serial_port") or profile_cfg.get("serial_port") or "")

    if role == "modbus-io":
        snapshot = await plugin.execute_command("read_io_snapshot", {})
        if not snapshot.get("success"):
            return {
                "module_role": role,
                "ok": False,
                "device_id": device_id,
                "serial_port": serial_port,
                "message": str(snapshot.get("error") or "read_io_snapshot failed"),
                "config_registers": [],
                "channels": [],
            }
        data = snapshot.get("data") or {}
        return {
            "module_role": role,
            "ok": True,
            "device_id": device_id,
            "serial_port": serial_port,
            "config_registers": _config_rows(data),
            "channels": _io_channel_rows(data),
        }

    read_result = await plugin.execute_command("read_all", {})
    config_result = await plugin.execute_command("read_config_snapshot", {})
    if not read_result.get("success"):
        return {
            "module_role": role,
            "ok": False,
            "device_id": device_id,
            "serial_port": serial_port,
            "message": str(read_result.get("error") or "read_all failed"),
            "config_registers": [],
            "channels": [],
        }
    data = read_result.get("data") or {}
    config_data = config_result.get("data") if config_result.get("success") else {}
    read_address = int(plugin._read_address())
    return {
        "module_role": role,
        "ok": True,
        "device_id": device_id,
        "serial_port": serial_port,
        "config_registers": _config_rows(config_data or {}),
        "channels": _adc_channel_rows(data, read_address),
    }


async def read_modbus_profile_channels(profile_id: str) -> dict[str, Any]:
    if profile_id not in MODBUS_PROFILE_IDS:
        profile_id = "modbus-adc"
    baud_settings = read_modbus_baud_settings(_settings)
    profile_cfg = baud_settings["profiles"][profile_id]
    health = await get_hardware_gateway().health()
    modules = []
    for role in profile_cfg.get("module_roles") or []:
        modules.append(await _read_module_channels(role, profile_cfg, health))
    successful = sum(1 for module in modules if module.get("ok"))
    if modules and successful == 0:
        raise OqlosError(
            code="hw_modbus_no_response",
            status_code=503,
            message="No Modbus profile modules responded",
            detail={"profile_id": profile_id, "modules": modules},
        )
    return {
        "ok": successful == len(modules) if modules else False,
        "profile_id": profile_id,
        "modules": modules,
    }


async def write_modbus_channel_value(payload: dict[str, Any]) -> dict[str, Any]:
    module_role = str(payload.get("module_role") or "").strip()
    write_type = str(payload.get("write_type") or "").strip()
    if module_role not in {"modbus-io", "modbus-adc"}:
        raise OqlosError(
            code="api_modbus_wizard_invalid_request",
            status_code=422,
            message="module_role must be modbus-io or modbus-adc",
            detail={"payload": payload},
        )
    if write_type not in {"coil", "holding_register"}:
        raise OqlosError(
            code="api_modbus_wizard_invalid_request",
            status_code=422,
            message="write_type must be coil or holding_register",
            detail={"payload": payload},
        )

    gateway = get_hardware_gateway()
    raw_value = payload.get("value")
    coil_off = write_type == "coil" and raw_value not in {
        True,
        1,
        "1",
        "true",
        "True",
        "on",
        "ON",
    }
    await ensure_power_safe(
        gateway,
        operation=f"{module_role}.{write_type}",
        safe_state=coil_off,
    )
    plugin = await gateway._get_or_connect_plugin(module_role)
    if plugin is None:
        raise OqlosError(
            code="hw_modbus_no_response",
            status_code=503,
            message=f"{module_role} plugin unavailable",
            detail={"module_role": module_role, "write_type": write_type},
        )

    if write_type == "coil":
        address = int(payload.get("address"))
        value = raw_value in {True, 1, "1", "true", "True", "on", "ON"}
        result = await plugin.execute_command("set_coil", {"coil": address, "value": value})
    else:
        result = await plugin.execute_command(
            "write_holding_register",
            {"address": int(payload.get("address")), "value": int(payload.get("value"))},
        )

    if not result.get("success"):
        raise OqlosError(
            code="hw_modbus_no_response",
            status_code=503,
            message=str(result.get("error") or "write failed"),
            detail={
                "module_role": module_role,
                "write_type": write_type,
                "result": result,
            },
        )
    return {"ok": True, "result": result.get("data") or {}}
