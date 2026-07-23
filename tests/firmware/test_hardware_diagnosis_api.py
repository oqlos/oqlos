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


def test_build_diagnosis_report_accepts_replaced_modbus_adc():
    identify = {
        "mode": "real",
        "platform": {
            "modbus_topology": "separate-adapters",
            "analog_input_driver_role": "usb-adc-stack",
            "modbus_adc_driver_role": "disabled",
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
    assert payload["devices"]["modbus-adc"]["status"] == "ok"
    assert payload["devices"]["modbus-adc"]["environment"]["replaced_by"] == "usb-adc-stack"
    assert payload["devices"]["modbus-adc"]["recommended_actions"] == []
