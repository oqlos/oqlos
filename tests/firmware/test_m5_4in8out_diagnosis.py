"""Diagnosis coverage for the M5 4In8Out valve module."""

from __future__ import annotations

from typing import Any

from oqlos.errors.catalog import ISSUE_CATALOG
from oqlos.hardware.diagnosis import _OQLOS_SAFE_PLUGINS, resolve_recover_plugin_ids
from oqlos.hardware.diagnosis_device_actions import (
    M5_4IN8OUT_PLUGIN_ID,
    diagnose_plugin_devices,
)


def _diagnose(health: dict[str, Any], adapters: dict[str, Any] | None = None) -> dict[str, Any]:
    return diagnose_plugin_devices(
        health,
        adapters or {},
        {},
        topology="boardnet",
        host_recover="",
    )


def test_module_is_absent_from_reports_until_it_is_configured() -> None:
    devices = _diagnose({"modbus-io": {"status": "ok", "compatible": True}})

    # Stands still on the RS485 module must not grow a permanent missing row.
    assert M5_4IN8OUT_PLUGIN_ID not in devices
    assert "modbus-io" in devices


def test_registry_only_optional_adapter_is_not_reported_as_offline() -> None:
    devices = _diagnose(
        {"modbus-io": {"status": "ok", "compatible": True}},
        {
            M5_4IN8OUT_PLUGIN_ID: {
                "id": M5_4IN8OUT_PLUGIN_ID,
                "optional": True,
                "status": "offline",
                "probe": {},
            }
        },
    )

    # The identify registry lists optional hardware for inventory purposes. It
    # is not proof that the plugin was enabled for this bench.
    assert M5_4IN8OUT_PLUGIN_ID not in devices


def test_configured_module_is_reported() -> None:
    devices = _diagnose(
        {M5_4IN8OUT_PLUGIN_ID: {"status": "connected", "compatible": True, "message": "ok"}}
    )

    assert devices[M5_4IN8OUT_PLUGIN_ID].display_name == "M5Stack Module 4In8Out"


def test_missing_bus_gets_i2c_specific_guidance() -> None:
    devices = _diagnose(
        {
            M5_4IN8OUT_PLUGIN_ID: {
                "status": "error",
                "compatible": False,
                "message": "cannot open /dev/i2c-1: No such file or directory",
            }
        }
    )
    device = devices[M5_4IN8OUT_PLUGIN_ID]

    assert any("I2C" in issue for issue in device.issues)
    action_ids = {action.id for action in device.recommended_actions}
    assert action_ids == {"m5-4in8out-physical", "m5-4in8out-reconnect"}
    # RS485 advice would be actively misleading for an I2C module.
    assert not any("RS485" in action.label for action in device.recommended_actions)


def test_silent_module_reports_wiring_check() -> None:
    devices = _diagnose(
        {
            M5_4IN8OUT_PLUGIN_ID: {
                "status": "error",
                "compatible": False,
                "message": "4In8Out probe failed: no answer from 4In8Out at 0x45",
            }
        }
    )
    device = devices[M5_4IN8OUT_PLUGIN_ID]

    assert any("SDA/SCL" in issue for issue in device.issues)


def test_missing_driver_package_is_named() -> None:
    devices = _diagnose(
        {
            M5_4IN8OUT_PLUGIN_ID: {
                "status": "incompatible",
                "compatible": False,
                "message": "m5-4in8out is not installed for the io-m5-4in8out plugin",
            }
        }
    )

    assert any(
        "sync_m5_4in8out" in issue for issue in devices[M5_4IN8OUT_PLUGIN_ID].issues
    )


def test_recover_selector_accepts_the_new_plugin() -> None:
    assert M5_4IN8OUT_PLUGIN_ID in _OQLOS_SAFE_PLUGINS
    assert resolve_recover_plugin_ids(M5_4IN8OUT_PLUGIN_ID) == (M5_4IN8OUT_PLUGIN_ID,)


def test_issue_codes_are_registered() -> None:
    assert "hw_m5_4in8out_no_response" in ISSUE_CATALOG
    assert "hw_m5_4in8out_bus_stale" in ISSUE_CATALOG
    assert "hw_tic249_position_uncertain" in ISSUE_CATALOG


def test_m5_plugin_health_maps_to_i2c_issue_code() -> None:
    from oqlos.api.plugins import _plugin_health_issue_code

    assert _plugin_health_issue_code("io-m5-4in8out") == "hw_m5_4in8out_no_response"
    assert _plugin_health_issue_code("modbus-io") == "hw_modbus_no_response"


def test_connected_tic249_with_uncertain_position_is_degraded() -> None:
    devices = _diagnose(
        {
            "motor-tic249": {
                "status": "connected",
                "compatible": True,
                "message": "Lung motor is healthy",
                "details": {
                    "runtime_status": {
                        "position_uncertain": True,
                        "reverse_limit_active": False,
                        "forward_limit_active": False,
                    }
                },
            }
        }
    )
    device = devices["motor-tic249"]

    assert device.status == "degraded"
    assert any("SDA" in issue for issue in device.issues)
    assert any(action.code == "hw_tic249_position_uncertain" for action in device.recommended_actions)


def test_connected_tic249_uncertain_at_reverse_limit_is_degraded() -> None:
    devices = _diagnose(
        {
            "motor-tic249": {
                "status": "connected",
                "compatible": True,
                "message": "Plugin is healthy",
                "details": {
                    "runtime_status": {
                        "position_uncertain": True,
                        "reverse_limit_active": True,
                        "forward_limit_active": False,
                    }
                },
            }
        }
    )
    device = devices["motor-tic249"]

    assert device.status == "degraded"
    assert any("homing" in issue for issue in device.issues)
    assert any(action.code == "hw_tic249_position_uncertain" for action in device.recommended_actions)


def test_disabled_m5_tells_operator_to_check_i2c() -> None:
    devices = _diagnose(
        {
            M5_4IN8OUT_PLUGIN_ID: {
                "status": "disabled",
                "compatible": False,
                "message": "Plugin is disabled in OqlOS configuration",
            }
        }
    )
    device = devices[M5_4IN8OUT_PLUGIN_ID]

    assert device.status == "error"
    assert any("0x45" in issue for issue in device.issues)


def test_optional_adapter_is_listed_in_the_hardware_registry() -> None:
    from oqlos.api.hardware_registry import HARDWARE_REGISTRY

    entry = next(hw for hw in HARDWARE_REGISTRY if hw["id"] == M5_4IN8OUT_PLUGIN_ID)

    assert entry["protocol"] == "HTTP/WiFi to CoreS3, then I2C"
    # Operators must see the module on identify even before it is wired.
    assert entry["optional"] is True


def test_dormant_optional_adapter_does_not_force_live_scans() -> None:
    from oqlos.api import hardware_probe

    healthy = {
        "modbus-io": {"compatible": True},
        "modbus-adc": {"compatible": True},
        "motor-tic249": {"compatible": True},
        "motor-dri0050": {"compatible": True},
    }

    # No health entry for the M5 module: it is simply not configured here, and
    # that must not be mistaken for a fault that triggers RS485/USB probing.
    assert hardware_probe._needs_live_scan(healthy) is False
    assert M5_4IN8OUT_PLUGIN_ID not in hardware_probe._unhealthy_plugin_ids(healthy)


def test_configured_optional_adapter_is_scanned_like_the_others() -> None:
    from oqlos.api import hardware_probe

    health = {
        "modbus-io": {"compatible": True},
        "modbus-adc": {"compatible": True},
        "motor-tic249": {"compatible": True},
        "motor-dri0050": {"compatible": True},
        M5_4IN8OUT_PLUGIN_ID: {"compatible": False, "status": "error"},
    }

    assert hardware_probe._needs_live_scan(health) is True
    assert M5_4IN8OUT_PLUGIN_ID in hardware_probe._unhealthy_plugin_ids(health)
