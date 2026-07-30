"""Tests for isolated Modbus wizard programming order."""

from __future__ import annotations

import asyncio
import time

import pytest

from oqlos.api import hardware as hw
from oqlos.api import hardware_modbus_routes as routes
from oqlos.api import hardware_modbus_topology as topology
from oqlos.api import hardware_modbus_waveshare as waveshare
from oqlos.api import hardware_modbus_wizard as wizard
from oqlos.errors import OqlosError


def _patch_modbus_ports(monkeypatch, ports: dict):
    monkeypatch.setattr(topology, "_modbus_runtime_serial_ports", lambda: ports)
    monkeypatch.setattr(hw, "_modbus_runtime_serial_ports", lambda: ports)


def _patch_modbus_io_ids(monkeypatch, ids: list[int]):
    monkeypatch.setattr(topology, "_modbus_io_device_ids", lambda: ids)
    monkeypatch.setattr(hw, "_modbus_io_device_ids", lambda: ids)


def _patch_modbus_settings(monkeypatch, settings_obj):
    monkeypatch.setattr(topology, "_settings", settings_obj)
    monkeypatch.setattr(waveshare, "_settings", settings_obj)
    monkeypatch.setattr(wizard, "_settings", settings_obj)


def _patch_diagnose_matrix(monkeypatch, fake_matrix):
    monkeypatch.setattr(waveshare, "_diagnose_shared_bus_matrix", fake_matrix)


def test_modbus_wizard_normalizes_short_module_roles():
    assert wizard.normalize_modbus_module_role("io") == "modbus-io"
    assert wizard.normalize_modbus_module_role("ADC") == "modbus-adc"
    assert wizard.normalize_modbus_module_role("modbus-io") == "modbus-io"
    assert wizard.normalize_modbus_module_role("unknown") == ""


def test_modbus_wizard_probe_uses_bounded_timeout_and_required_role(monkeypatch):
    captured: dict[str, object] = {}

    class _Report:
        def to_dict(self):
            return {"ok": False, "hits": [], "issues": []}

    def fake_diagnose(**kwargs):
        captured.update(kwargs)
        return _Report()

    monkeypatch.setattr("pimodbus.repair.diagnose_shared_bus", fake_diagnose)

    result = wizard._modbus_wizard_probe_isolated(
        "/dev/ttyTEST",
        [9600],
        ["N"],
        [1],
        ["modbus-io"],
    )

    assert result["ok"] is False
    assert captured["timeout"] == wizard.MODBUS_ISOLATED_PROBE_TIMEOUT
    assert captured["required_roles"] == ["modbus-io"]


def test_modbus_wizard_program_writes_uart_before_address_change(monkeypatch):
    from pimodbus import provisioning as pim_prov

    calls: list[tuple[str, int]] = []

    class _Config:
        device_id = 1
        baudrate = 9600
        parity = "N"
        software_version = "V2.00"

        def to_dict(self):
            return {
                "device_id": self.device_id,
                "baudrate": self.baudrate,
                "parity": self.parity,
                "software_version": self.software_version,
            }

    def _read_config(_settings, *, device_id: int):
        cfg = _Config()
        cfg.device_id = device_id
        return cfg

    def _write_uart(_settings, *, device_id: int, **_kwargs):
        calls.append(("uart", device_id))
        return True

    def _write_address(_settings, *, current_device_id: int, new_device_id: int, **_kwargs):
        calls.append(("address", current_device_id))
        return True

    monkeypatch.setattr(pim_prov, "read_device_config", _read_config)
    monkeypatch.setattr(pim_prov, "write_uart_config", _write_uart)
    monkeypatch.setattr(pim_prov, "write_device_address", _write_address)
    monkeypatch.setattr(pim_prov, "uart_register_value", lambda *_a, **_k: 0x0101)
    class _Client:
        def close(self):
            return None

    monkeypatch.setattr(pim_prov, "_open_client", lambda *_a, **_k: _Client())
    monkeypatch.setattr(pim_prov, "_read_holding_register", lambda *_a, **_k: None)
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)

    result = wizard._modbus_wizard_program_isolated(
        serial_port="/dev/ttyTEST",
        current_device_id=1,
        new_device_id=2,
        new_baudrate=9600,
        new_parity="N",
        confirm_isolated=True,
    )

    assert result["ok"] is True
    assert calls[0] == ("uart", 1)
    assert ("address", 1) in calls


def test_modbus_wizard_program_skips_when_already_at_target(monkeypatch):
    from pimodbus import provisioning as pim_prov

    class _Config:
        def to_dict(self):
            return {"device_id": 2, "baudrate": 9600, "parity": "N", "software_version": None}

    monkeypatch.setattr(pim_prov, "read_device_config", lambda *_a, **_k: _Config())

    result = wizard._modbus_wizard_program_isolated(
        serial_port="/dev/ttyTEST",
        current_device_id=2,
        new_device_id=2,
        new_baudrate=9600,
        new_parity="N",
        confirm_isolated=True,
    )

    assert result["ok"] is True
    assert result["writes"]["skipped"] is True


def test_modbus_wizard_never_reports_success_without_verified_readback():
    result = wizard._wizard_build_result(
        {"set_address": True, "set_uart": True},
        {},
        False,
        1,
        4800,
        "N",
        "/dev/ttyTEST",
        "readback_failed",
        "hw_modbus_no_response",
    )

    assert result["ok"] is False
    assert result["verified"] is False
    assert result["error"] == "readback_failed"
    assert result["issue_code"] == "hw_modbus_no_response"


def test_modbus_wizard_readback_failure_uses_stable_reason() -> None:
    def _fail(*_args, **_kwargs):
        raise OSError("password=hunter2 /srv/private")

    verified, verify, reason, issue_code = wizard._wizard_verify_config(
        _fail,
        object(),
        1,
        4800,
        "N",
    )

    assert verified is False
    assert verify == {}
    assert reason == "readback_failed"
    assert issue_code == "modbus_preflight_exception"
    assert "hunter2" not in reason


@pytest.mark.parametrize(
    ("message", "issue_code"),
    [
        ("device did not respond", "hw_modbus_no_response"),
        ("serial port is busy password=hunter2", "serial_port_busy"),
        ("unexpected adapter failure", "modbus_preflight_exception"),
    ],
)
def test_modbus_wizard_classifies_exception_without_publishing_message(
    message: str,
    issue_code: str,
) -> None:
    assert wizard._modbus_wizard_issue_for_exception(OSError(message)) == issue_code


def test_modbus_wizard_rejects_empty_config_instead_of_skipping(monkeypatch):
    from pimodbus import provisioning as pim_prov

    class _EmptyConfig:
        def to_dict(self):
            return {
                "device_id": None,
                "baudrate": None,
                "parity": None,
                "software_version": None,
            }

    monkeypatch.setattr(pim_prov, "read_device_config", lambda *_a, **_k: _EmptyConfig())

    result = wizard._modbus_wizard_program_isolated(
        serial_port="/dev/ttyTEST",
        current_device_id=1,
        new_device_id=1,
        new_baudrate=4800,
        new_parity="N",
        confirm_isolated=True,
        current_baudrate=9600,
    )

    assert result["ok"] is False
    assert result["verified"] is False
    assert result["open_baud_tried"] == [9600, 4800]
    assert result["error"] == "invalid_config_reply"
    assert result["issue_code"] == "hw_modbus_no_response"


def test_build_waveshare_diagnose_uses_target_baud_fast_path(monkeypatch):
    calls: list[dict[str, object]] = []

    class _Report:
        def __init__(self, ok: bool):
            self.ok = ok

        def to_dict(self):
            return {"ok": self.ok, "hits": [], "issues": []}

    def _fake_matrix(**kwargs):
        calls.append(kwargs)
        return _Report(ok=len(calls) == 1)

    _patch_modbus_ports(monkeypatch, {
        "io_serial_port": "/dev/ttyTEST",
        "adc_serial_port": "/dev/ttyTEST",
        "topology": "shared-bus",
    })
    _patch_diagnose_matrix(monkeypatch, _fake_matrix)
    _patch_modbus_io_ids(monkeypatch, [1])
    _patch_modbus_settings(
        monkeypatch,
        type(
            "S",
            (),
            {
                "modbus_serial_port": "/dev/ttyTEST",
                "modbus_adc_serial_port": "/dev/ttyTEST",
                "modbus_baud": 9600,
                "modbus_parity": "N",
                "modbus_device_id": 1,
                "modbus_adc_device_id": 2,
            },
        )(),
    )
    monkeypatch.setattr(waveshare, "effective_modbus_target_baud", lambda _settings: 9600)

    result = hw._build_waveshare_diagnose_report()
    assert result["ok"] is False
    assert result["overall_status"] == "degraded"
    assert result["waveshare_scan"]["ok"] is True
    assert len(calls) == 1
    assert calls[0]["serial_port"] == "/dev/ttyTEST"
    assert calls[0]["target_baudrate"] == 9600


def test_build_waveshare_diagnose_scans_separate_adapters(monkeypatch):
    from pimodbus import provisioning as pim_prov

    calls: list[str] = []

    class _Report:
        def __init__(self, ok: bool, role: str, serial: str):
            self.ok = ok
            self._role = role
            self._serial = serial

        def to_dict(self):
            return {
                "ok": self.ok,
                "hits": [
                    {
                        "role": self._role,
                        "serial_port": self._serial,
                        "baudrate": 9600,
                        "parity": "N",
                        "device_id": 1 if self._role == "modbus-io" else 2,
                        "function": "read_coils" if self._role == "modbus-io" else "read_input_registers",
                    }
                ],
                "issues": [],
            }

    def _fake_matrix(*, serial_port: str, required_roles=None, **_kwargs):
        calls.append(serial_port)
        role = (required_roles or ["modbus-io"])[0]
        return _Report(True, role, serial_port)

    _patch_modbus_ports(monkeypatch, {
        "io_serial_port": "/dev/ttyIO",
        "adc_serial_port": "/dev/ttyADC",
        "topology": "separate-adapters",
    })
    _patch_diagnose_matrix(monkeypatch, _fake_matrix)

    class _Cfg:
        def to_dict(self):
            return {"device_id": 1, "baudrate": 9600, "parity": "N"}

    _patch_modbus_io_ids(monkeypatch, [1])
    monkeypatch.setattr(pim_prov, "read_device_config", lambda *_a, **_k: _Cfg())
    monkeypatch.setattr(waveshare, "_read_output_control_modes", lambda *_a, **_k: {"ok": True})
    _patch_modbus_settings(
        monkeypatch,
        type(
            "S",
            (),
            {
                "modbus_serial_port": "/dev/ttyIO",
                "modbus_adc_serial_port": "/dev/ttyADC",
                "modbus_baud": 9600,
                "modbus_parity": "N",
                "modbus_device_id": 1,
                "modbus_adc_device_id": 2,
            },
        )(),
    )

    result = hw._build_waveshare_diagnose_report()
    assert result["topology"] == "separate-adapters"
    assert result["ok"] is True
    assert result["overall_status"] == "healthy"
    assert calls == ["/dev/ttyIO", "/dev/ttyADC"]
    assert result["waveshare_scan"]["ports_scanned"] == [
        {"role": "modbus-io", "serial_port": "/dev/ttyIO"},
        {"role": "modbus-adc", "serial_port": "/dev/ttyADC"},
    ]


def test_build_waveshare_skips_matrix_when_plugins_healthy(monkeypatch):
    calls: list[str] = []

    def _fake_matrix(*, serial_port: str, **_kwargs):
        calls.append(serial_port)
        raise AssertionError("matrix scan should be skipped")

    _patch_diagnose_matrix(monkeypatch, _fake_matrix)
    _patch_modbus_ports(monkeypatch, {
        "io_serial_port": "/dev/ttyIO",
        "adc_serial_port": "/dev/ttyADC",
        "topology": "separate-adapters",
    })
    _patch_modbus_io_ids(monkeypatch, [2])
    _patch_modbus_settings(
        monkeypatch,
        type(
            "S",
            (),
            {
                "modbus_serial_port": "/dev/ttyIO",
                "modbus_adc_serial_port": "/dev/ttyADC",
                "modbus_baud": 9600,
                "modbus_parity": "N",
                "modbus_device_id": 2,
                "modbus_adc_device_id": 2,
            },
        )(),
    )

    health = {
        "modbus-io": {
            "compatible": True,
            "status": "connected",
            "message": "healthy password=hunter2 /srv/private",
        },
        "modbus-adc": {
            "compatible": True,
            "status": "connected",
            "message": "healthy password=hunter2 /srv/private",
        },
    }
    result = hw._build_waveshare_diagnose_report(health)
    assert result["ok"] is True
    assert result["overall_status"] == "healthy"
    assert result.get("plugin_health_deferred") is True
    assert calls == []
    assert result["per_slave"]["modbus-io-2"]["status"] == "connected"
    assert result["waveshare_scan"]["scan_skipped"] is True
    assert "hunter2" not in str(result)
    assert "/srv/private" not in str(result)


def test_build_waveshare_serial_stale_skips_matrix(monkeypatch):
    def _fake_matrix(**_kwargs):
        raise AssertionError("matrix scan should be skipped for stale serial")

    _patch_diagnose_matrix(monkeypatch, _fake_matrix)
    _patch_modbus_ports(monkeypatch, {
        "io_serial_port": "/dev/ttyIO",
        "adc_serial_port": "/dev/ttyADC",
        "topology": "separate-adapters",
    })
    _patch_modbus_io_ids(monkeypatch, [2])
    _patch_modbus_settings(
        monkeypatch,
        type(
            "S",
            (),
            {
                "modbus_serial_port": "/dev/ttyIO",
                "modbus_adc_serial_port": "/dev/ttyADC",
                "modbus_baud": 9600,
                "modbus_parity": "N",
                "modbus_device_id": 2,
                "modbus_adc_device_id": 2,
            },
        )(),
    )
    health = {
        "modbus-io": {
            "compatible": False,
            "message": "Health check exception: [Errno 5] Input/output error password=hunter2",
        },
        "modbus-adc": {
            "compatible": False,
            "message": "Health check exception: [Errno 5] Input/output error /srv/private",
        },
    }
    result = hw._build_waveshare_diagnose_report(health)
    assert result.get("serial_handles_stale") is True
    assert result["overall_status"] == "unavailable"
    assert result["waveshare_scan"]["scan_skipped"] is True
    assert result["per_slave"]["modbus-io-2"]["status"] == "serial-stale"
    assert result["code"] == result["error_code"] == "C2004-HW-0012"
    assert result["diagnostics"]["issue_code"] == "hw_modbus_serial_handle_stale"
    assert result["waveshare_scan"]["issues"][0]["public_code"] == "C2004-HW-0012"
    assert "hunter2" not in str(result)
    assert "/srv/private" not in str(result)


def test_waveshare_control_mode_failure_is_classified_and_sanitized(monkeypatch):
    import pymodbus.client

    class _Client:
        def __init__(self, **_kwargs):
            pass

        def connect(self):
            return True

        def read_holding_registers(self, **_kwargs):
            raise OSError("serial port is busy password=hunter2 /srv/private")

        def close(self):
            raise RuntimeError("close password=hunter2")

    monkeypatch.setattr(pymodbus.client, "ModbusSerialClient", _Client)

    result = waveshare._read_output_control_modes(
        "/dev/password=hunter2", 9600, "N", 1
    )

    assert result["status"] == "read-error"
    assert result["reason"] == "control-register-read-failed"
    assert result["error_code"] == "C2004-HW-0013"
    assert result["diagnostics"]["issue_code"] == "serial_port_busy"
    assert "hunter2" not in str(result)
    assert "/srv/private" not in str(result)


def test_waveshare_control_mode_missing_dependency_is_sanitized(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name.startswith("pymodbus"):
            raise ModuleNotFoundError("password=hunter2 /srv/private")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    result = waveshare._read_output_control_modes("/dev/ttyTEST", 9600, "N", 1)

    assert result["status"] == "dependency-unavailable"
    assert result["error_code"] == "C2004-HW-0012"
    assert result["diagnostics"]["issue_code"] == "pimodbus_unavailable"
    assert "hunter2" not in str(result)
    assert "/srv/private" not in str(result)


def test_waveshare_control_mode_programming_error_is_not_masked(monkeypatch):
    import pymodbus.client

    class _Client:
        def __init__(self, **_kwargs):
            pass

        def connect(self):
            return True

        def read_holding_registers(self, **_kwargs):
            raise AttributeError("programming defect")

        def close(self):
            return None

    monkeypatch.setattr(pymodbus.client, "ModbusSerialClient", _Client)

    with pytest.raises(AttributeError, match="programming defect"):
        waveshare._read_output_control_modes("/dev/ttyTEST", 9600, "N", 1)


@pytest.mark.parametrize(
    ("reader", "device_id", "hits", "port"),
    [
        (
            waveshare._read_waveshare_io_slave_config,
            1,
            [{"role": "modbus-io", "device_id": 1, "serial_port": "/dev/ttyIO"}],
            "/dev/ttyIO",
        ),
        (
            waveshare._read_waveshare_adc_slave_config,
            2,
            [{"role": "modbus-adc", "device_id": 2, "serial_port": "/dev/ttyADC"}],
            "/dev/ttyADC",
        ),
    ],
)
def test_waveshare_device_config_failure_is_sanitized(
    monkeypatch, reader, device_id, hits, port
):
    from pimodbus import provisioning as pim_prov

    def _fail(*_args, **_kwargs):
        raise RuntimeError("password=hunter2 /srv/private")

    monkeypatch.setattr(pim_prov, "read_device_config", _fail)

    result = reader(device_id, hits, port, 9600, "N")

    assert result["status"] == "read-error"
    assert result["reason"] == "device-config-read-failed"
    assert result["error_code"] == "C2004-HW-0012"
    assert result["diagnostics"]["issue_code"] == "modbus_preflight_exception"
    assert "hunter2" not in str(result)
    assert "/srv/private" not in str(result)


def test_modbus_wizard_probe_raises_when_pimodbus_missing(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name.startswith("pimodbus"):
            raise ModuleNotFoundError("password=hunter2 /srv/private")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)
    with pytest.raises(OqlosError) as caught:
        wizard._modbus_wizard_probe_isolated("/dev/ttyTEST", [4800], ["N"], [1])
    assert caught.value.issue_code == "pimodbus_unavailable"
    assert caught.value.public_code == "C2004-HW-0012"
    assert "hunter2" not in caught.value.message
    assert caught.value.detail == {
        "architecture": "SOA",
        "layer": "firmware",
        "component": "modbus-wizard",
        "stage": "dependency.load",
        "problem_source": "dependency",
        "operation_id": "modbus.wizard.probe-isolated",
        "upstream_target": "python-package://pimodbus",
    }


def test_build_waveshare_raises_when_pimodbus_missing(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name.startswith("pimodbus"):
            raise ModuleNotFoundError("password=hunter2 /srv/private")
        return real_import(name, *args, **kwargs)

    _patch_modbus_ports(monkeypatch, {
        "io_serial_port": "/dev/ttyIO",
        "adc_serial_port": "/dev/ttyADC",
        "topology": "separate-adapters",
    })
    _patch_modbus_io_ids(monkeypatch, [1])
    _patch_modbus_settings(
        monkeypatch,
        type(
            "S",
            (),
            {
                "modbus_serial_port": "/dev/ttyIO",
                "modbus_adc_serial_port": "/dev/ttyADC",
                "modbus_baud": 4800,
                "modbus_parity": "N",
                "modbus_device_id": 1,
                "modbus_adc_device_id": 2,
            },
        )(),
    )
    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    with pytest.raises(OqlosError) as caught:
        hw._build_waveshare_diagnose_report({"modbus-io": {"compatible": False}})

    assert caught.value.issue_code == "pimodbus_unavailable"
    assert caught.value.public_code == "C2004-HW-0012"
    assert caught.value.status_code == 503
    assert "hunter2" not in caught.value.message
    assert caught.value.detail == {
        "architecture": "SOA",
        "layer": "firmware",
        "component": "modbus-waveshare",
        "stage": "dependency.load",
        "problem_source": "dependency",
        "operation_id": "modbus.waveshare.diagnose",
        "upstream_target": "python-package://pimodbus",
    }


def test_build_waveshare_adapter_failure_is_typed_and_sanitized(monkeypatch):
    _patch_modbus_ports(
        monkeypatch,
        {
            "io_serial_port": "/dev/password=hunter2",
            "adc_serial_port": "/dev/password=hunter2",
            "topology": "shared-bus",
        },
    )
    _patch_modbus_io_ids(monkeypatch, [1])
    _patch_modbus_settings(
        monkeypatch,
        type(
            "S",
            (),
            {
                "modbus_serial_port": "/dev/password=hunter2",
                "modbus_adc_serial_port": "/dev/password=hunter2",
                "modbus_baud": 9600,
                "modbus_parity": "N",
                "modbus_device_id": 1,
                "modbus_adc_device_id": 2,
            },
        )(),
    )

    def _fail(*_args, **_kwargs):
        raise OSError("serial port is busy password=hunter2 /srv/private")

    monkeypatch.setattr(waveshare, "_probe_waveshare_shared_bus", _fail)

    with pytest.raises(OqlosError) as caught:
        waveshare._build_waveshare_diagnose_report()

    assert caught.value.status_code == 409
    assert caught.value.issue_code == "serial_port_busy"
    assert caught.value.public_code == "C2004-HW-0013"
    assert caught.value.detail["component"] == "modbus-waveshare"
    assert caught.value.detail["stage"] == "matrix.scan"
    assert caught.value.detail["upstream_target"] == (
        "serial-device://configured-adapter"
    )
    assert "hunter2" not in caught.value.message


def test_modbus_runtime_ports_auto_detects_separate_adapters(monkeypatch):
    monkeypatch.delenv("OQLOS_MODBUS_TOPOLOGY", raising=False)
    monkeypatch.setenv("OQLOS_MODBUS_SERIAL_PORT", "/dev/io")
    monkeypatch.setenv("OQLOS_MODBUS_ADC_SERIAL_PORT", "/dev/adc")
    ports = hw._modbus_runtime_serial_ports()
    assert ports["topology"] == "separate-adapters"
    assert ports["topology_mode"] == "auto"


def test_modbus_runtime_ports_shared_bus_forced(monkeypatch):
    monkeypatch.setenv("OQLOS_MODBUS_TOPOLOGY", "shared-bus")
    monkeypatch.setenv("OQLOS_MODBUS_SERIAL_PORT", "/dev/io")
    monkeypatch.setenv("OQLOS_MODBUS_ADC_SERIAL_PORT", "/dev/adc")
    ports = hw._modbus_runtime_serial_ports()
    assert ports["topology"] == "shared-bus"
    assert ports["io_serial_port"] == "/dev/io"
    assert ports["adc_serial_port"] == "/dev/io"


def test_modbus_wizard_plan_exposes_per_adapter_ports(monkeypatch):
    _patch_modbus_ports(monkeypatch, {
        "io_serial_port": "/dev/ttyIO",
        "adc_serial_port": "/dev/ttyADC",
        "topology": "separate-adapters",
    })
    _patch_modbus_io_ids(monkeypatch, [1, 2])
    _patch_modbus_settings(
        monkeypatch,
        type("S", (), {
            "modbus_baud": 9600,
            "modbus_parity": "N",
            "modbus_device_id": 1,
            "modbus_adc_device_id": 2,
            "modbus_serial_port": "/dev/ttyIO",
            "modbus_adc_serial_port": "/dev/ttyADC",
        })(),
    )
    plan = hw._modbus_wizard_plan()
    assert plan["topology"] == "separate-adapters"
    assert plan["io_serial_port"] == "/dev/ttyIO"
    assert plan["adc_serial_port"] == "/dev/ttyADC"
    io_step = next(step for step in plan["steps"] if step["step"] == "configure-modbus-io-1")
    adc_step = next(step for step in plan["steps"] if step["step"] == "configure-modbus-adc-2")
    assert io_step["serial_port"] == "/dev/ttyIO"
    assert adc_step["serial_port"] == "/dev/ttyADC"


def test_modbus_wizard_plan_route_does_not_depend_on_thread_pool(monkeypatch):
    expected = {"ok": True, "steps": []}
    monkeypatch.setattr(routes, "_modbus_wizard_plan", lambda: expected)

    async def forbidden_to_thread(*_args, **_kwargs):
        raise AssertionError("configuration-only plan must not use the hardware thread pool")

    monkeypatch.setattr(routes.asyncio, "to_thread", forbidden_to_thread)

    assert asyncio.run(routes.hardware_modbus_wizard_plan()) == expected
