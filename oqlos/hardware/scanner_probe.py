"""Barcode / keyboard-wedge scanner detection for hardware identify."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BARCODE_SCANNER_ID = "barcode-scanner"

_USB_STRONG_HINTS = (
    "scanner",
    "barcode",
    "bar code",
    "qr",
    "symbol",
    "honeywell",
    "zebra",
    "datalogic",
    "tera",
    "racal",
    "code reader",
    "2d scanner",
    "0581:011c",
)
_WEDGE_KEYBOARD_HINTS = ("holtek", "usb-hid keyboard")
_INPUT_NAME_HINTS = _USB_STRONG_HINTS + ("wedge",)
_INPUT_EXCLUDE_HINTS = (
    "sleep button",
    "power button",
    "video bus",
    "hdmi",
    "nvidia",
    "audio",
    "mx anywhere",
    "logitech",
    "yubico",
    "security key",
    "consumer control",
    "system control",
    " keyboard mouse",
    " keyboard consumer",
)
_USB_EXCLUDE_HINTS = (
    "pololu",
    "tic t249",
    "tic249",
    "hub",
    "yubico",
    "logitech",
    "nvidia",
    "audio",
)


def _join_blob(source: dict[str, Any], keys: tuple[str, ...]) -> str:
    return " ".join(str(source.get(key) or "") for key in keys).strip()


def _match_blob(item: dict[str, str]) -> str:
    return _join_blob(item, ("id", "name", "product", "manufacturer", "description", "handlers", "path"))


def _is_likely_scanner_usb_blob(blob: str) -> bool:
    low = blob.lower()
    if any(excluded in low for excluded in _USB_EXCLUDE_HINTS):
        return False
    if any(hint in low for hint in _USB_STRONG_HINTS + _WEDGE_KEYBOARD_HINTS):
        return True
    if "crw" in low:
        return any(token in low for token in ("scanner", "barcode", "reader", "magnetic"))
    return False


def _is_likely_scanner_input(name: str, handlers: str) -> bool:
    if not handlers:
        return False
    lowered = f"{name} {handlers}".lower()
    if any(excluded in lowered for excluded in _INPUT_EXCLUDE_HINTS):
        return False
    if any(hint in lowered for hint in _INPUT_NAME_HINTS):
        return True
    if any(hint in lowered for hint in _WEDGE_KEYBOARD_HINTS) and "kbd" in handlers:
        return "keyboard" in lowered and "mouse" not in lowered
    return False


def _usb_product_blob(device: dict[str, Any]) -> str:
    return _join_blob(device, ("manufacturer", "product", "description", "id", "vendor_id", "product_id", "path"))


def _canonical_match_key(item: dict[str, str]) -> str:
    blob = _match_blob(item).lower()
    if "holtek" in blob or "04d9:a231" in blob:
        return "wedge:holtek"
    hwid = str(item.get("id") or "").strip().lower()
    if hwid:
        return f"usb:{hwid}"
    name = str(item.get("name") or "").strip().lower()
    if name:
        return f"input:{name}"
    return blob or "unknown"


def _match_priority(item: dict[str, str]) -> int:
    blob = _match_blob(item).lower()
    priority = 20
    if "holtek" in blob or "04d9:a231" in blob:
        priority = 100
    elif any(hint in blob for hint in ("barcode", "scanner", "wedge", "qr", "symbol", "zebra", "honeywell", "datalogic")):
        priority = 90
    elif "usb-hid keyboard" in blob:
        priority = 50
    elif "crw" in blob:
        priority = 5
    if item.get("source") == "oqlos-diagnostics":
        priority += 2
    return priority


def _merge_matches(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    best_by_key: dict[str, tuple[int, dict[str, str]]] = {}
    for group in groups:
        for item in group:
            key = _canonical_match_key(item)
            priority = _match_priority(item)
            current = best_by_key.get(key)
            if current is None or priority > current[0]:
                best_by_key[key] = (priority, item)
    merged = [entry for _, entry in best_by_key.values()]
    merged.sort(key=_match_priority, reverse=True)
    return merged


def _scan_lsusb_matches() -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    try:
        result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=2, check=False)
        for line in result.stdout.splitlines():
            if not _is_likely_scanner_usb_blob(line):
                continue
            parts = line.split("ID ", 1)
            hwid = parts[1].split(" ", 1)[0] if len(parts) > 1 else ""
            matches.append({"id": hwid, "description": line.strip(), "source": "lsusb"})
    except Exception:
        return matches
    return matches


def _scan_input_matches() -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    devices_path = Path("/proc/bus/input/devices")
    if not devices_path.exists():
        return matches
    try:
        blocks = devices_path.read_text(encoding="utf-8", errors="ignore").split("\n\n")
        for block in blocks:
            name = ""
            handlers = ""
            for raw in block.splitlines():
                line = raw.strip()
                if line.startswith("N: Name="):
                    name = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("H: Handlers="):
                    handlers = line.split("=", 1)[1].strip()
            if _is_likely_scanner_input(name, handlers):
                matches.append({"name": name, "handlers": handlers, "source": "input"})
    except Exception:
        return matches
    return matches


def _scan_diagnostics_usb_matches(diagnostics: dict[str, Any] | None) -> list[dict[str, str]]:
    if not isinstance(diagnostics, dict):
        return []
    raw_devices = diagnostics.get("usb_devices")
    if not isinstance(raw_devices, list):
        return []
    matches: list[dict[str, str]] = []
    for device in raw_devices:
        if not isinstance(device, dict):
            continue
        blob = _usb_product_blob(device)
        if not blob or not _is_likely_scanner_usb_blob(blob):
            continue
        vendor = str(device.get("vendor_id") or "")
        product_id = str(device.get("product_id") or "")
        hwid = f"{vendor}:{product_id}" if vendor and product_id else ""
        matches.append(
            {
                "id": hwid,
                "manufacturer": str(device.get("manufacturer") or ""),
                "product": str(device.get("product") or ""),
                "path": str(device.get("path") or ""),
                "source": "oqlos-diagnostics",
            }
        )
    return matches


def resolve_scanner_presence(diagnostics: dict[str, Any] | None = None) -> tuple[bool, dict[str, Any]]:
    matched_devices = _merge_matches(
        _scan_lsusb_matches(),
        _scan_diagnostics_usb_matches(diagnostics),
        _scan_input_matches(),
    )
    detail = {
        "scanner_present": bool(matched_devices),
        "matched_devices": matched_devices,
        "usb_devices": _scan_lsusb_matches() + _scan_diagnostics_usb_matches(diagnostics),
        "input_devices": _scan_input_matches(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    return bool(matched_devices), detail


def build_scanner_adapter_entry(diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    present, detail = resolve_scanner_presence(diagnostics)
    primary = detail["matched_devices"][0] if detail["matched_devices"] else {}
    label = str(primary.get("product") or primary.get("name") or "").strip()
    if not label:
        description = str(primary.get("description") or "").strip()
        if " ID " in description:
            label = description.split(" ID ", 1)[-1].strip()
            if " " in label:
                label = label.split(" ", 1)[-1].strip()
        elif description:
            label = description
    name = f"Skaner kodów — {label}" if label else "Skaner kodów kreskowych"
    return {
        "id": BARCODE_SCANNER_ID,
        "name": name,
        "protocol": "USB HID / Keyboard Wedge",
        "status": "ok" if present else "adapter-only",
        "detail": detail,
        "probe": {
            "connected": present,
            "source": "oqlos.hardware.scanner_probe",
            "primary_match": primary or None,
        },
    }


def enrich_scanner_adapter(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else None
    entry = build_scanner_adapter_entry(diagnostics)
    adapters = list(payload.get("adapters") or [])
    existing = next((adapter for adapter in adapters if adapter.get("id") == BARCODE_SCANNER_ID), None)
    if existing:
        existing.update(entry)
    else:
        adapters.append(entry)
    payload["adapters"] = adapters
    payload["total"] = len(adapters)
    healthy = {"ok", "adapter-only"}
    payload["detected"] = sum(1 for adapter in adapters if adapter.get("status") in healthy)
    return payload
