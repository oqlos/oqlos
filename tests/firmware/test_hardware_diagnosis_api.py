"""Regression: /api/v1/hardware/diagnosis and /recover."""

from __future__ import annotations

import asyncio

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


def test_modbus_timeout_is_no_response_not_stale():
    """RTU read timeout must not be labeled as serial_handle_stale."""
    identify = {
        "mode": "real",
        "platform": {
            "modbus_topology": "separate-adapters",
            "modbus_io_serial_port": "/dev/ttyUSB2",
            "modbus_adc_serial_port": "/dev/ttyUSB1",
            "serial_ports": ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2"],
        },
        "diagnostics": {
            "health": {
                "modbus-io": {
                    "status": "error",
                    "compatible": False,
                    "message": "Modbus RTU read_coils timed out after 2.0s",
                },
                "modbus-adc": {
                    "status": "error",
                    "compatible": False,
                    "message": "Modbus ADC read_input_registers timed out after 2.0s",
                },
                "motor-tic249": {"status": "connected", "compatible": True, "message": "ok"},
                "motor-dri0050": {"status": "connected", "compatible": True, "message": "ok"},
            },
        },
        "adapters": [],
    }
    report = build_diagnosis_report(identify)
    payload = report_to_dict(report)
    assert payload["ok"] is False
    assert payload["environment"].get("serial_handles_stale") in (False, None)
    for pid in ("modbus-io", "modbus-adc"):
        dev = payload["devices"][pid]
        assert dev["status"] == "error"
        assert dev["issues"], f"{pid} should expose operator issues"
        assert "nie odpowiada" in dev["issues"][0].lower() or "slave" in dev["issues"][0].lower() or "modbus" in dev["issues"][0].lower()
        codes = [a.get("code") for a in dev["recommended_actions"]]
        assert "hw_modbus_device_no_response" in codes
        assert "hw_modbus_serial_handle_stale" not in codes
        assert dev["environment"].get("failure_kind") == "device_no_response"


def test_modbus_errno19_is_stale_handle():
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
    assert any(a.get("code") == "hw_modbus_serial_handle_stale" for a in actions)


def test_filter_motors_recomputes_ok_and_message():
    from oqlos.hardware.diagnosis import filter_diagnosis_dict_for_devices

    payload = {
        "ok": False,
        "message": "Diagnostyka: wymaga uwagi — modbus-io, modbus-adc",
        "requires_full_stack_restart": True,
        "devices": {
            "modbus-io": {"device_id": "modbus-io", "status": "error"},
            "modbus-adc": {"device_id": "modbus-adc", "status": "error"},
            "motor-tic249": {"device_id": "motor-tic249", "status": "ok"},
            "motor-dri0050": {"device_id": "motor-dri0050", "status": "ok"},
        },
        "global_actions": [
            {"id": "global-modbus-recover", "device_id": "*", "kind": "make_target"},
        ],
    }
    filtered = filter_diagnosis_dict_for_devices(payload, "motors")
    assert set(filtered["devices"]) == {"motor-tic249", "motor-dri0050"}
    assert filtered["ok"] is True
    assert "modbus" not in filtered["message"].lower()
    assert filtered["requires_full_stack_restart"] is False
    assert filtered["global_actions"] == []
