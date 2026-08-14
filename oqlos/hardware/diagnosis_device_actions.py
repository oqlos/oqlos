"""Per-device diagnosis builders and global recovery actions."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.diagnosis_plugin_health import infer_status, message_lower
from oqlos.hardware.diagnosis_types import DeviceDiagnosis, DiagnosisAction

_MONITORED_PLUGINS = (
    ("modbus-io", "Waveshare Modbus IO 8CH"),
    ("io-m5-4in8out", "M5Stack Module 4In8Out"),
    ("modbus-adc", "Waveshare Modbus ADC 8CH"),
    ("motor-tic249", "Pololu Tic T249"),
    ("motor-dri0050", "DFRobot DRI0050"),
)

M5_4IN8OUT_PLUGIN_ID = "io-m5-4in8out"


def add_m5_4in8out_device_actions(dev: DeviceDiagnosis, status: str, msg: str) -> None:
    """I2C failures need different hands-on checks than an RS485 module."""
    if status == "ok":
        return
    if "no such file or directory" in msg or "/dev/i2c" in msg:
        dev.issues.append(
            "Brak magistrali I2C na hoście — włącz I2C (raspi-config) i sprawdź /dev/i2c-1."
        )
    if "remote i/o error" in msg or "errno 121" in msg or "no answer" in msg:
        dev.issues.append(
            "Moduł nie odpowiada pod adresem I2C — zasilanie 9-24 V, SDA/SCL i wspólne GND."
        )
    if "not installed" in msg or "no module named" in msg:
        dev.issues.append(
            "Brak sterownika m5-4in8out w venv OqlOS — uruchom krok deployu sync_m5_4in8out."
        )
    dev.recommended_actions.append(
        DiagnosisAction(
            id="m5-4in8out-physical",
            device_id=M5_4IN8OUT_PLUGIN_ID,
            label="Sprawdź I2C: i2cdetect -y 1 (oczekiwany adres 0x45)",
            kind="manual",
            priority=20,
            auto_executable=False,
            scope="host",
            detail=(
                "Moduł zasilany z własnego portu 9-24 V; do Pi idą tylko SDA (GPIO2), "
                "SCL (GPIO3) i wspólne GND. Wejścia IN1-IN4 przyjmują wyłącznie styk "
                "bezpotencjałowy."
            ),
            code="hw_m5_4in8out_no_response",
            actuation_risk="none",
        )
    )
    dev.recommended_actions.append(
        DiagnosisAction(
            id="m5-4in8out-reconnect",
            device_id=M5_4IN8OUT_PLUGIN_ID,
            label="Reconnect plugin io-m5-4in8out (OqlOS)",
            kind="oqlos",
            priority=15,
            auto_executable=True,
            scope="oqlos",
            detail="Ponowne otwarcie magistrali I2C w procesie OqlOS (bez zmiany stanu wyjść).",
            code="hw_m5_4in8out_bus_stale",
            actuation_risk="none",
        )
    )


def add_modbus_device_actions(
    dev: DeviceDiagnosis,
    plugin_id: str,
    status: str,
    msg: str,
    platform: dict[str, Any],
) -> None:
    port = (
        platform.get("modbus_io_serial_port")
        if plugin_id == "modbus-io"
        else platform.get("modbus_adc_serial_port")
    )
    dev.environment["serial_port"] = port
    if status == "ok":
        return
    if "errno 19" in msg or "no such device" in msg:
        dev.issues.append("Nieaktualny port USB/RS485 po re-enumeracji.")
    timed_out = "timed out" in msg or "timeout" in msg or "no response" in msg
    if timed_out:
        dev.issues.append(
            "Moduł Modbus nie odpowiada na RTU — zasilanie, A/B, GND, slave ID, baud 4800."
        )
        dev.recommended_actions.append(
            DiagnosisAction(
                id=f"{plugin_id}-physical",
                device_id=plugin_id,
                label="Sprawdź zasilanie / RS485 / slave ID (baud 4800)",
                kind="manual",
                priority=20,
                auto_executable=False,
                scope="host",
                detail=(
                    "Sonda baud/parity/ID bez odpowiedzi. Reconnect OqlOS nie pomoże — "
                    "sprawdź 12/24V, A/B, wspólne GND i DIP slave (plan: ID=1, 4800 8N1)."
                ),
                code="hw_modbus_no_response",
                actuation_risk="none",
            )
        )
        return
    dev.recommended_actions.append(
        DiagnosisAction(
            id=f"{plugin_id}-reconnect",
            device_id=plugin_id,
            label=f"Reconnect plugin {plugin_id} (OqlOS)",
            kind="oqlos",
            priority=15,
            auto_executable=True,
            scope="oqlos",
            detail="Bezpieczne odświeżenie połączenia w procesie OqlOS.",
            code="hw_modbus_serial_handle_stale",
            actuation_risk="none",
        )
    )


def _sidecar_recovery_actions(
    device_id: str,
    *,
    ensure_id: str,
    ensure_label: str,
    ensure_detail: str,
    reconnect_id: str,
    reconnect_label: str,
    issue_code: str | None = None,
) -> list[DiagnosisAction]:
    """Standard pair of in-process OqlOS actions offered for every motor sidecar."""
    return [
        DiagnosisAction(
            id=ensure_id,
            device_id=device_id,
            label=ensure_label,
            kind="oqlos",
            priority=5,
            auto_executable=True,
            scope="oqlos",
            detail=ensure_detail,
            code=issue_code,
            actuation_risk="config" if issue_code else None,
        ),
        DiagnosisAction(
            id=reconnect_id,
            device_id=device_id,
            label=reconnect_label,
            kind="oqlos",
            priority=18,
            auto_executable=True,
            scope="oqlos",
        ),
    ]


def add_tic249_device_actions(
    dev: DeviceDiagnosis,
    status: str,
    msg: str,
    host_recover: str,
    entry: dict[str, Any] | None = None,
) -> None:
    details = (entry or {}).get("details") if isinstance((entry or {}).get("details"), dict) else {}
    runtime = details.get("runtime_status") if isinstance(details.get("runtime_status"), dict) else {}
    uncertain = bool(runtime.get("position_uncertain"))
    reverse = bool(runtime.get("reverse_limit_active"))
    forward = bool(runtime.get("forward_limit_active"))
    if uncertain:
        dev.status = "degraded"
        if not reverse and not forward:
            dev.issues.append(
                "Pozycja silnika niepewna i żadna krańcówka nie jest aktywna — "
                "sprawdź SDA (reverse) oraz homing przed ruchem AL."
            )
        else:
            dev.issues.append("Pozycja silnika niepewna — wykonaj homing do krańcówki.")
        dev.environment.update(
            {
                "position_uncertain": True,
                "reverse_limit_active": reverse,
                "forward_limit_active": forward,
            }
        )
        dev.recommended_actions.append(
            DiagnosisAction(
                id="tic249-limit-wiring",
                device_id=dev.device_id,
                label="Sprawdź krańcówkę reverse (SDA) i NVM pinów Tic249",
                kind="manual",
                priority=12,
                auto_executable=False,
                scope="host",
                detail=(
                    "Sidecar :8205 jest online, ale position_uncertain=true. "
                    "Reconnect USB nie pomoże — sprawdź krańcówkę reverse, pull-up i profil NVM."
                ),
                code="hw_tic249_position_uncertain",
                actuation_risk="none",
            )
        )
    if status == "ok" and not uncertain:
        return
    if status != "ok":
        if "errno 19" in msg:
            dev.issues.append("USB Tic — martwy handle po replug.")
        if "connection attempts failed" in msg or "503" in msg or "connect returned false" in msg:
            dev.issues.append(
                "Sidecar hw-tic249 (:8205) niedostępny — OqlOS zrestartuje usługę systemd --user."
            )
        dev.recommended_actions.extend(
            _sidecar_recovery_actions(
                dev.device_id,
                ensure_id="tic249-ensure-sidecar",
                ensure_label="Restart hw-tic249.service (OqlOS)",
                ensure_detail="systemctl --user restart hw-tic249.service, potem reconnect USB Tic (bez ruchu silnika).",
                reconnect_id="tic249-oqlos-reconnect",
                reconnect_label="Reconnect motor-tic249 plugin (OqlOS)",
                issue_code="hw_tic249_sidecar_unreachable",
            )
        )


def add_dri0050_device_actions(
    dev: DeviceDiagnosis,
    status: str,
    msg: str,
    host_recover: str,
) -> None:
    if status == "ok":
        return
    if "connection attempts failed" in msg or "503" in msg:
        dev.issues.append(
            "Sidecar DRI0050 (:8203) niedostępny lub /health=503 — OqlOS uruchomi ponownie systemd-run."
        )
    if "errno 5" in msg or "input/output error" in msg:
        dev.issues.append("Martwy handle USB RS485 pompy — odłącz/podłącz kabel pompy.")
    dev.recommended_actions.extend(
        _sidecar_recovery_actions(
            dev.device_id,
            ensure_id="dri0050-ensure-sidecar",
            ensure_label="Uruchom dri0050-motor-api (OqlOS)",
            ensure_detail="systemd-run jak make hardware-up, bez restartu całego stacku.",
            reconnect_id="dri0050-reconnect",
            reconnect_label="Reconnect motor-dri0050 plugin (OqlOS)",
            issue_code="hw_dri0050_sidecar_unreachable",
        )
    )


def _modbus_adc_is_replaced(plugin_id: str, platform: dict[str, Any]) -> bool:
    """Hide the legacy Modbus ADC when dedicated USB/UART ADCs own AI inputs."""
    if plugin_id != "modbus-adc":
        return False
    analog_driver = str(platform.get("analog_input_driver_role") or "").strip().lower()
    driver_role = str(platform.get("modbus_adc_driver_role") or "").strip().lower()
    return (
        bool(analog_driver and analog_driver != "modbus-adc")
        or driver_role in {"disabled", "replaced"}
    )


def _mock_motor_diagnosis(
    plugin_id: str, display_name: str, entry: dict[str, Any] | None, topology: str,
    hardware_mode: str,
) -> DeviceDiagnosis | None:
    if str(hardware_mode or "").lower() != "mock" or not plugin_id.startswith("motor") or entry is not None:
        return None
    return DeviceDiagnosis(
        device_id=plugin_id,
        display_name=display_name,
        status="ok",
        health_summary="symulator OqlOS (mock)",
        environment={"topology": topology, "hardware_mode": "mock"},
    )


def _add_plugin_actions(
    dev: DeviceDiagnosis, plugin_id: str, status: str, message: str,
    platform: dict[str, Any], host_recover: str,
    entry: dict[str, Any] | None = None,
) -> None:
    if plugin_id.startswith("modbus"):
        add_modbus_device_actions(dev, plugin_id, status, message, platform)
    elif plugin_id == M5_4IN8OUT_PLUGIN_ID:
        add_m5_4in8out_device_actions(dev, status, message)
    elif plugin_id == "motor-tic249":
        add_tic249_device_actions(dev, status, message, host_recover, entry)
    elif plugin_id == "motor-dri0050":
        add_dri0050_device_actions(dev, status, message, host_recover)


def _standard_plugin_diagnosis(
    plugin_id: str, display_name: str, entry: dict[str, Any] | None,
    adapter: dict[str, Any] | None, platform: dict[str, Any], topology: str,
    host_recover: str,
) -> DeviceDiagnosis:
    status = infer_status(plugin_id, entry, present=entry is not None or adapter is not None)
    dev = DeviceDiagnosis(
        device_id=plugin_id,
        display_name=display_name,
        status=status,
        health_summary=str((entry or {}).get("message") or (adapter or {}).get("status") or "brak danych"),
        environment={"topology": topology},
    )
    _add_plugin_actions(
        dev, plugin_id, status, message_lower(entry), platform, host_recover, entry,
    )
    return dev


def diagnose_plugin_devices(
    health: dict[str, Any], adapters: dict[str, Any], platform: dict[str, Any],
    topology: str, host_recover: str, *, hardware_mode: str = "",
) -> dict[str, DeviceDiagnosis]:
    """Build diagnosis only for devices active in the selected topology."""
    devices: dict[str, DeviceDiagnosis] = {}
    for plugin_id, display_name in _MONITORED_PLUGINS:
        if _modbus_adc_is_replaced(plugin_id, platform):
            continue
        entry = health.get(plugin_id) if isinstance(health.get(plugin_id), dict) else None
        # The identify registry always lists optional inventory adapters, so
        # only a health entry proves that M5 is enabled for this bench.
        if plugin_id == M5_4IN8OUT_PLUGIN_ID and entry is None:
            continue
        special = _mock_motor_diagnosis(plugin_id, display_name, entry, topology, hardware_mode)
        devices[plugin_id] = special or _standard_plugin_diagnosis(
            plugin_id, display_name, entry, adapters.get(plugin_id), platform, topology, host_recover,
        )
    return devices


def diagnose_barcode_scanner(adapters: dict[str, Any]) -> DeviceDiagnosis:
    """Build barcode scanner diagnosis entry."""
    adapter = adapters.get("barcode-scanner")
    detail = (adapter or {}).get("detail") if isinstance((adapter or {}).get("detail"), dict) else {}
    present = bool(detail.get("scanner_present")) or str((adapter or {}).get("status") or "") == "ok"
    return DeviceDiagnosis(
        device_id="barcode-scanner",
        display_name="Skaner USB-HID",
        status="ok" if present else "not_present",
        health_summary="Wykryty" if present else "Brak skanera",
    )


def diagnose_analog_input_devices(
    identify: dict[str, Any],
    platform: dict[str, Any],
) -> dict[str, DeviceDiagnosis]:
    """Expose health of the dedicated MCP2221/DFR1184 analog-input stack."""
    if platform.get("analog_input_driver_role") != "usb-adc-stack":
        return {}
    diagnostics = identify.get("diagnostics")
    stack_health = (
        diagnostics.get("analog_input_health")
        if isinstance(diagnostics, dict)
        and isinstance(diagnostics.get("analog_input_health"), dict)
        else {}
    )
    components = (
        stack_health.get("components")
        if isinstance(stack_health.get("components"), dict)
        else {}
    )
    parent_error = str(stack_health.get("message") or "brak danych health usb-adc-stack")
    devices: dict[str, DeviceDiagnosis] = {}
    for spec in platform.get("analog_input_devices") or []:
        if not isinstance(spec, dict) or not spec.get("device_id"):
            continue
        device_id = str(spec["device_id"])
        entry = components.get(device_id)
        component = entry if isinstance(entry, dict) else {}
        if component.get("ok") is True:
            status = "ok"
        elif stack_health:
            status = "error"
        else:
            status = "unknown"
        message = str(component.get("message") or parent_error)
        dev = DeviceDiagnosis(
            device_id=device_id,
            display_name=(
                "Microchip MCP2221A ADC"
                if device_id == "usb-adc-mcp2221"
                else "DFRobot DFR1184 ADC"
            ),
            status=status,
            health_summary=message,
            environment={
                "inputs": list(spec.get("inputs") or []),
                "physical_inputs": list(spec.get("physical_inputs") or []),
                **({"transport": component.get("transport")} if component.get("transport") else {}),
                **({"endpoint": component.get("endpoint")} if component.get("endpoint") else {}),
            },
        )
        if status == "error":
            dev.issues.append(message)
            if device_id == "usb-adc-dfr1184":
                dev.recommended_actions.append(
                    DiagnosisAction(
                        id="dfr1184-uart-physical",
                        device_id=device_id,
                        label="Sprawdź zasilanie, tryb UART oraz TX/RX/GND DFR1184",
                        kind="manual",
                        priority=20,
                        auto_executable=False,
                        scope="host",
                        detail=(
                            "Wyłącz zasilanie przed zmianą przełącznika. DFR1184: UART, "
                            "9600 8N1; Pi TXD pin 8 → C/R, Pi RXD pin 10 ← D/T, wspólne GND."
                        ),
                        code="hw_usb_adc_sidecar_unreachable",
                        actuation_risk="physical",
                    )
                )
        devices[device_id] = dev
    return devices


def build_report_global_actions(
    modbus_bad: bool,
    motors_bad: bool,
    c2004_root: str,
    host_recover: str,
) -> list[DiagnosisAction]:
    """Build the global recovery actions for the full stack restart path."""
    global_actions: list[DiagnosisAction] = []
    if modbus_bad and motors_bad:
        global_actions.append(
            DiagnosisAction(
                id="global-stack-restart",
                device_id="*",
                label="make hardware-up",
                kind="make_target",
                priority=10,
                make_target="hardware-up",
                command=f"cd {c2004_root} && make hardware-up",
                auto_executable=bool(host_recover),
                scope="host",
            )
        )
    elif modbus_bad:
        global_actions.append(
            DiagnosisAction(
                id="global-modbus-recover",
                device_id="*",
                label="make hardware-up (Modbus)",
                kind="make_target",
                priority=12,
                make_target="hardware-up",
                command=f"cd {c2004_root} && make hardware-up",
                auto_executable=bool(host_recover),
                scope="host",
            )
        )
    return global_actions
