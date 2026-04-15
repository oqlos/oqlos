"""Firmware health check and identification."""

from __future__ import annotations

from .discovery import list_usb_serial_devices, list_i2c_buses, detect_chips_on_i2c


def check_firmware_health(url: str = "http://localhost:8202") -> dict:
    """Check firmware health via HTTP API."""
    try:
        import httpx
        r = httpx.get(f"{url}/api/v1/hardware/health", timeout=5.0)
        return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def check_firmware_identify(url: str = "http://localhost:8202") -> dict:
    """Get detailed hardware identification."""
    try:
        import httpx
        r = httpx.get(f"{url}/api/v1/hardware/identify", timeout=20.0)
        return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def cmd_health(url: str = "http://localhost:8202") -> str:
    """Health command — check firmware health, return formatted string."""
    health = check_firmware_health(url)
    output = ["\n🏥 HARDWARE HEALTH", "─" * 50]

    if "error" in health:
        output.append(f"❌ Error: {health['error']}")
    else:
        mode = health.get("mode", "unknown")
        output.append(f"Mode: {mode.upper()}")
        for key, val in health.items():
            if key != "mode":
                status = "✅" if val in ["ok", "connected", True] else "⚠️"
                output.append(f"  {status} {key}: {val}")

    return "\n".join(output)


def cmd_diagnose(url: str = "http://localhost:8202") -> str:
    """Full diagnostic command — combines USB + I2C + health + identify."""
    from .report import format_peripheral_table

    output = ["\n" + "=" * 60, "HARDWARE DIAGNOSTIC REPORT", "=" * 60]

    # USB & I2C
    output.append("\n🔌 USB/SERIAL PERIPHERALS")
    output.append(format_peripheral_table(list_usb_serial_devices()))
    output.append("\n📡 I2C BUSES")
    buses = list_i2c_buses()
    if buses:
        for bus in buses:
            chips = detect_chips_on_i2c(bus)
            chip_str = f" ({len(chips)} chips)" if chips else ""
            output.append(f"  {bus}{chip_str}")
            for chip in chips[:5]:
                output.append(f"    └─ Address {chip['address']}")
    else:
        output.append("  No I2C buses detected.")

    # Health
    output.append(cmd_health(url))

    # Identify
    import json as _json
    identify = check_firmware_identify(url)
    if "error" not in identify:
        output.append("\n🔍 FIRMWARE IDENTIFY")
        output.append("─" * 50)
        output.append(_json.dumps(identify, indent=2, default=str))

    output.append("\n" + "=" * 60)
    return "\n".join(output)
