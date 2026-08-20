"""Regression: /api/v1/hardware/diagnosis and /recover."""

from __future__ import annotations

from oqlos.hardware.diagnosis import build_diagnosis_report, report_to_dict


def test_build_diagnosis_report_motors_error():
    identify = {
        "platform": {"modbus_topology": "separate-adapters"},
        "diagnostics": {
            "health": {
                "modbus-io": {"status": "connected", "compatible": True, "message": "ok"},
                "modbus-adc": {"status": "connected", "compatible": True, "message": "ok"},
                "motor-tic249": {
                    "status": "error",
                    "compatible": False,
                    "message": "[Errno 19] No such device",
                },
                "motor-dri0050": {
                    "status": "error",
                    "compatible": False,
                    "message": "HTTP 503",
                },
            },
        },
        "adapters": [],
    }
    report = build_diagnosis_report(identify)
    payload = report_to_dict(report)
    assert payload["ok"] is False
    assert payload["devices"]["motor-tic249"]["status"] == "error"
    tic249_actions = payload["devices"]["motor-tic249"]["recommended_actions"]
    assert any(
        a["id"] == "tic249-ensure-sidecar" and a["scope"] == "oqlos" and a["auto_executable"]
        for a in tic249_actions
    )
    ensure_action = next(a for a in tic249_actions if a["id"] == "tic249-ensure-sidecar")
    assert ensure_action["code"] == "hw_tic249_sidecar_unreachable"
    assert ensure_action["actuation_risk"] == "config"


def test_motors_only_no_global_make_hardware_up():
    identify = {
        "platform": {"modbus_topology": "separate-adapters"},
        "diagnostics": {
            "health": {
                "modbus-io": {"status": "connected", "compatible": True, "message": "ok"},
                "modbus-adc": {"status": "connected", "compatible": True, "message": "ok"},
                "motor-dri0050": {
                    "status": "error",
                    "compatible": False,
                    "message": "All connection attempts failed",
                },
            },
        },
        "adapters": [],
    }
    report = build_diagnosis_report(identify)
    payload = report_to_dict(report)
    global_make = [a for a in payload["global_actions"] if a.get("make_target") == "hardware-up"]
    assert global_make == []
    dri = payload["devices"]["motor-dri0050"]
    assert any(a["id"] == "dri0050-ensure-sidecar" for a in dri["recommended_actions"])
    assert not any(str(a.get("command") or "").startswith("systemctl") for a in dri["recommended_actions"])


def test_recover_targets_skip_devices_ok_in_report():
    from oqlos.hardware.diagnosis import DiagnosisReport, DeviceDiagnosis, _recover_targets

    report = DiagnosisReport(
        environment={},
        devices={
            "modbus-io": DeviceDiagnosis(
                device_id="modbus-io",
                display_name="IO",
                status="ok",
                health_summary="ok",
            ),
            "motor-dri0050": DeviceDiagnosis(
                device_id="motor-dri0050",
                display_name="DRI",
                status="error",
                health_summary="down",
            ),
        },
        global_actions=[],
        ok=False,
        message="",
    )
    health = {
        "modbus-io": {"status": "error", "compatible": False, "message": "transient"},
        "motor-dri0050": {"status": "error", "compatible": False, "message": "down"},
    }
    targets = _recover_targets(report, health)
    assert targets == ["motor-dri0050"]


def test_recover_targets_include_degraded_device_with_a_safe_auto_action():
    """Regression: after the M5 migration modbus-io is `degraded`, not `error`, so
    its advertised auto-executable reconnect was never executed."""
    from oqlos.hardware.diagnosis import DiagnosisReport, DeviceDiagnosis, _recover_targets
    from oqlos.hardware.diagnosis_types import DiagnosisAction

    reconnect = DiagnosisAction(
        id="modbus-io-reconnect",
        device_id="modbus-io",
        label="Reconnect plugin modbus-io (OqlOS)",
        kind="oqlos",
        priority=15,
        auto_executable=True,
        scope="oqlos",
        actuation_risk="none",
    )
    manual = DiagnosisAction(
        id="tic249-limit-wiring",
        device_id="motor-tic249",
        label="Check the reverse limit switch",
        kind="manual",
        priority=12,
        auto_executable=False,
        scope="host",
        actuation_risk="none",
    )
    report = DiagnosisReport(
        environment={},
        devices={
            "modbus-io": DeviceDiagnosis(
                device_id="modbus-io",
                display_name="IO",
                status="degraded",
                health_summary="Plugin health is unavailable",
                recommended_actions=[reconnect],
            ),
            "motor-tic249": DeviceDiagnosis(
                device_id="motor-tic249",
                display_name="Tic",
                status="degraded",
                health_summary="Plugin is healthy",
                recommended_actions=[manual],
            ),
        },
        global_actions=[],
        ok=True,
        message="",
    )
    health = {
        "modbus-io": {"status": "error", "compatible": False, "message": "not connected"},
        "motor-tic249": {"status": "error", "compatible": False, "message": "position uncertain"},
    }

    # Only the device whose repair is in-process and risk-free is reconnected;
    # a manual host action stays a recommendation.
    assert _recover_targets(report, health) == ["modbus-io"]


def test_still_failed_plugins_skip_intentionally_disabled_modbus_adc():
    from oqlos.hardware.diagnosis import (
        DiagnosisReport,
        DeviceDiagnosis,
        _still_failed_plugins,
    )

    report = DiagnosisReport(
        environment={},
        devices={
            "modbus-io": DeviceDiagnosis(
                device_id="modbus-io",
                display_name="IO",
                status="error",
                health_summary="down",
            ),
            "modbus-adc": DeviceDiagnosis(
                device_id="modbus-adc",
                display_name="ADC",
                status="ok",
                health_summary="Disabled as expected",
            ),
        },
        global_actions=[],
        ok=False,
        message="",
    )
    health = {
        "modbus-io": {"status": "error", "compatible": False, "message": "down"},
        "modbus-adc": {"status": "disabled", "compatible": False, "message": "disabled"},
    }

    assert _still_failed_plugins(
        report,
        health,
        ("modbus-io", "modbus-adc"),
    ) == ["modbus-io"]


def test_host_actions_filtered_motor_only_no_make():
    from oqlos.hardware.diagnosis import DiagnosisReport, _host_actions_from_report

    report = DiagnosisReport(
        environment={},
        devices={},
        global_actions=[],
        ok=False,
        message="",
        requires_full_stack_restart=False,
    )
    host = _host_actions_from_report(report, still_failed=["motor-dri0050"])
    assert not any(a.get("kind") == "make_target" for a in host)


def test_build_diagnosis_report_mock_motors_without_health():
    identify = {
        "mode": "mock",
        "platform": {"modbus_topology": "separate-adapters"},
        "diagnostics": {"health": {}},
        "adapters": [],
    }
    report = build_diagnosis_report(identify)
    payload = report_to_dict(report)
    assert payload["environment"]["hardware_mode"] == "mock"
    assert payload["devices"]["motor-tic249"]["status"] == "ok"
    assert "mock" in payload["devices"]["motor-tic249"]["health_summary"].lower()
    assert payload["devices"]["motor-tic249"]["recommended_actions"] == []


def test_build_diagnosis_report_omits_replaced_modbus_adc():
    identify = {
        "mode": "real",
        "platform": {
            "modbus_topology": "separate-adapters",
            "analog_input_driver_role": "usb-adc-stack",
            "modbus_adc_driver_role": "disabled",
            "analog_input_devices": [
                {
                    "device_id": "usb-adc-mcp2221",
                    "inputs": ["ai01"],
                },
                {
                    "device_id": "usb-adc-dfr1184",
                    "inputs": ["ai02", "ai03"],
                },
            ],
        },
        "diagnostics": {
            "health": {
                "modbus-io": {
                    "status": "connected",
                    "compatible": True,
                    "message": "Modbus RTU is healthy",
                },
                "modbus-adc": {
                    "status": "disabled",
                    "compatible": False,
                    "message": "Plugin is disabled in OqlOS configuration",
                },
                "motor-tic249": {"status": "connected", "compatible": True, "message": "ok"},
                "motor-dri0050": {"status": "connected", "compatible": True, "message": "ok"},
            },
        },
        "adapters": [],
    }

    payload = report_to_dict(build_diagnosis_report(identify))

    assert payload["ok"] is True
    assert payload["requires_full_stack_restart"] is False
    assert payload["global_actions"] == []
    assert "modbus-adc" not in payload["devices"]
    assert payload["environment"]["analog_input_devices"] == [
        {"device_id": "usb-adc-mcp2221", "inputs": ["ai01"]},
        {"device_id": "usb-adc-dfr1184", "inputs": ["ai02", "ai03"]},
    ]


def test_build_diagnosis_report_surfaces_partial_usb_adc_failure():
    identify = {
        "mode": "real",
        "platform": {
            "modbus_topology": "separate-adapters",
            "analog_input_driver_role": "usb-adc-stack",
            "modbus_adc_driver_role": "disabled",
            "analog_input_devices": [
                {
                    "device_id": "usb-adc-mcp2221",
                    "inputs": ["ai01"],
                    "physical_inputs": ["MCP2221A.G1"],
                },
                {
                    "device_id": "usb-adc-dfr1184",
                    "inputs": ["ai02", "ai03"],
                    "physical_inputs": ["DFR1184.AIN1", "DFR1184.AIN2"],
                },
            ],
        },
        "diagnostics": {
            "health": {
                "modbus-io": {"status": "connected", "compatible": True},
                "motor-tic249": {"status": "connected", "compatible": True},
                "motor-dri0050": {"status": "connected", "compatible": True},
            },
            "analog_input_health": {
                "ok": False,
                "status": "degraded",
                "components": {
                    "usb-adc-mcp2221": {
                        "ok": True,
                        "status": "connected",
                        "message": "MCP2221 ready",
                    },
                    "usb-adc-dfr1184": {
                        "ok": False,
                        "status": "unavailable",
                        "message": "UART response truncated: expected 4 bytes, received 0",
                        "transport": "uart",
                        "endpoint": "/dev/serial0",
                    },
                },
            },
        },
        "adapters": [],
    }

    payload = report_to_dict(build_diagnosis_report(identify))

    assert payload["ok"] is False
    assert payload["devices"]["usb-adc-mcp2221"]["status"] == "ok"
    dfr = payload["devices"]["usb-adc-dfr1184"]
    assert dfr["status"] == "error"
    assert dfr["environment"]["endpoint"] == "/dev/serial0"
    assert dfr["recommended_actions"][0]["id"] == "dfr1184-uart-physical"
    assert "usb-adc-dfr1184" in payload["message"]


def test_modbus_io_timeout_recommends_physical_not_stale_reconnect():
    identify = {
        "platform": {
            "modbus_topology": "separate-adapters",
            "modbus_io_serial_port": "/dev/serial/by-id/usb-io",
        },
        "diagnostics": {
            "health": {
                "modbus-io": {
                    "status": "error",
                    "compatible": False,
                    "message": "Modbus RTU read_coils timed out after 2.0s",
                },
                "modbus-adc": {"status": "connected", "compatible": True, "message": "ok"},
                "motor-tic249": {"status": "connected", "compatible": True, "message": "ok"},
                "motor-dri0050": {"status": "connected", "compatible": True, "message": "ok"},
            },
        },
        "adapters": [],
    }
    payload = report_to_dict(build_diagnosis_report(identify))
    actions = payload["devices"]["modbus-io"]["recommended_actions"]
    assert any(a["id"] == "modbus-io-physical" and a["code"] == "hw_modbus_no_response" for a in actions)
    assert not any(a["id"] == "modbus-io-reconnect" for a in actions)
    assert any("nie odpowiada" in i.lower() for i in payload["devices"]["modbus-io"]["issues"])


def test_modbus_io_stale_handle_still_recommends_reconnect():
    identify = {
        "platform": {"modbus_topology": "separate-adapters"},
        "diagnostics": {
            "health": {
                "modbus-io": {
                    "status": "error",
                    "compatible": False,
                    "message": "[Errno 19] No such device",
                },
                "modbus-adc": {"status": "connected", "compatible": True, "message": "ok"},
                "motor-tic249": {"status": "connected", "compatible": True, "message": "ok"},
                "motor-dri0050": {"status": "connected", "compatible": True, "message": "ok"},
            },
        },
        "adapters": [],
    }
    payload = report_to_dict(build_diagnosis_report(identify))
    actions = payload["devices"]["modbus-io"]["recommended_actions"]
    assert any(a["id"] == "modbus-io-reconnect" and a["code"] == "hw_modbus_serial_handle_stale" for a in actions)
    assert not any(a["id"] == "modbus-io-physical" for a in actions)
