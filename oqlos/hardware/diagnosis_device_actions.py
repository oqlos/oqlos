"""Per-device diagnosis builders and global recovery actions."""

from __future__ import annotations

from typing import Any

from oqlos.hardware.diagnosis_plugin_health import infer_status, message_lower
from oqlos.hardware.diagnosis_types import DeviceDiagnosis, DiagnosisAction


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
        )
    )


def add_tic249_device_actions(
    dev: DeviceDiagnosis,
    status: str,
    msg: str,
    host_recover: str,
) -> None:
    if status == "ok":
        return
    if "errno 19" in msg:
        dev.issues.append("USB Tic — martwy handle po replug.")
    if "connection attempts failed" in msg or "503" in msg or "connect returned false" in msg:
        dev.issues.append(
            "Sidecar hw-tic249 (:8205) niedostępny — OqlOS zrestartuje usługę systemd --user."
        )
    dev.recommended_actions.extend(
        [
            DiagnosisAction(
                id="tic249-ensure-sidecar",
                device_id=dev.device_id,
                label="Restart hw-tic249.service (OqlOS)",
                kind="oqlos",
                priority=5,
                auto_executable=True,
                scope="oqlos",
                detail="systemctl --user restart hw-tic249.service, potem reconnect USB Tic (bez ruchu silnika).",
            ),
            DiagnosisAction(
                id="tic249-oqlos-reconnect",
                device_id=dev.device_id,
                label="Reconnect motor-tic249 plugin (OqlOS)",
                kind="oqlos",
                priority=18,
                auto_executable=True,
                scope="oqlos",
            ),
        ]
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
        [
            DiagnosisAction(
                id="dri0050-ensure-sidecar",
                device_id=dev.device_id,
                label="Uruchom dri0050-motor-api (OqlOS)",
                kind="oqlos",
                priority=5,
                auto_executable=True,
                scope="oqlos",
                detail="systemd-run jak make hardware-up, bez restartu całego stacku.",
            ),
            DiagnosisAction(
                id="dri0050-reconnect",
                device_id=dev.device_id,
                label="Reconnect motor-dri0050 plugin (OqlOS)",
                kind="oqlos",
                priority=18,
                auto_executable=True,
                scope="oqlos",
            ),
        ]
    )


def diagnose_plugin_devices(
    health: dict[str, Any],
    adapters: dict[str, Any],
    platform: dict[str, Any],
    topology: str,
    host_recover: str,
) -> dict[str, DeviceDiagnosis]:
    """Build per-device diagnosis for the four monitored hardware plugins."""
    devices: dict[str, DeviceDiagnosis] = {}
    for plugin_id, display_name in (
        ("modbus-io", "Waveshare Modbus IO 8CH"),
        ("modbus-adc", "Waveshare Modbus ADC 8CH"),
        ("motor-tic249", "Pololu Tic T249"),
        ("motor-dri0050", "DFRobot DRI0050"),
    ):
        entry = health.get(plugin_id) if isinstance(health.get(plugin_id), dict) else None
        adapter = adapters.get(plugin_id)
        status = infer_status(plugin_id, entry, present=entry is not None or adapter is not None)
        dev = DeviceDiagnosis(
            device_id=plugin_id,
            display_name=display_name,
            status=status,
            health_summary=str(
                (entry or {}).get("message") or (adapter or {}).get("status") or "brak danych"
            ),
            environment={"topology": topology},
        )
        msg = message_lower(entry)
        if plugin_id.startswith("modbus"):
            add_modbus_device_actions(dev, plugin_id, status, msg, platform)
        elif plugin_id == "motor-tic249":
            add_tic249_device_actions(dev, status, msg, host_recover)
        elif plugin_id == "motor-dri0050":
            add_dri0050_device_actions(dev, status, msg, host_recover)
        devices[plugin_id] = dev
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
