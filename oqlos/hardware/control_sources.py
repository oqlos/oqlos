"""Persistent controller selection shared by the API and hardware plugins."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

LOCK = asyncio.Lock()
DEFAULTS = {"pump": "boardnet", "stepper": "boardnet", "valves": "auto"}
MOTOR_DEVICES = {"motor-dri0050": "pump", "motor-tic249": "stepper"}


def config_path() -> Path:
    return Path(os.environ.get(
        "OQLOS_CONTROL_SOURCES_PATH",
        str(Path.home() / ".config/oqlos/control-sources.json"),
    ))


import math

def validate(sources: dict[str, str]) -> None:
    if set(sources) != set(DEFAULTS):
        raise ValueError("Wymagane są ustawienia pompy, silnika krokowego i zaworów.")
    for key, value in sources.items():
        if key == "valves":
            allowed = {"boardnet", "stacknet", "auto"}
        elif key in ("pump", "stepper"):
            allowed = {"boardnet", "stacknet", "displaynet"}
        else:
            allowed = {"boardnet", "stacknet"}
        if not isinstance(value, str) or value not in allowed:
            raise ValueError(f"Nieprawidłowy kontroler urządzenia: {key}.")


def snapshot() -> dict:
    path = config_path()
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raw = b""
        sources = dict(DEFAULTS)
    else:
        # An existing, empty file is damaged configuration, not a request
        # to silently move control back to the default hardware.
        sources = json.loads(raw)
    if not isinstance(sources, dict):
        raise ValueError("Nieprawidłowa konfiguracja sterowania.")
    validate(sources)
    return {"sources": sources, "revision": hashlib.sha256(raw).hexdigest()}


def source(device: str) -> str:
    return snapshot()["sources"][device]


def save(sources: dict[str, str]) -> dict:
    validate(sources)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".pending")
    try:
        pending.write_text(json.dumps(sources, sort_keys=True) + "\n")
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)
    return snapshot()


def displaynet_url(device_or_plugin: str) -> str:
    if device_or_plugin in ("pump", "motor-dri0050"):
        return os.environ.get(
            "STACKNET_DRI0050_SIDECAR_URL",
            os.environ.get("DRI0050_SIDECAR_URL", "http://127.0.0.1:8203"),
        ).rstrip("/")
    if device_or_plugin in ("stepper", "motor-tic249"):
        return os.environ.get(
            "STACKNET_TIC249_SIDECAR_URL",
            os.environ.get("TIC249_SIDECAR_URL", "http://127.0.0.1:8205"),
        ).rstrip("/")
    raise ValueError(f"Nieznane urządzenie DisplayNet: {device_or_plugin}")


async def _execute_displaynet_command(device_or_plugin: str, command: str, params: dict | None = None) -> dict:
    import httpx

    params = params or {}
    base_url = displaynet_url(device_or_plugin)
    is_pump = device_or_plugin in ("pump", "motor-dri0050")

    if is_pump:
        if command == "status":
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"{base_url}/api/v1/dri0050")
                    if resp.status_code == 404:
                        resp = await client.get(f"{base_url}/api/status")
                    resp.raise_for_status()
                    data = resp.json()
            except Exception as exc:
                return {"success": False, "error": f"DisplayNet DRI0050 status unavailable: {exc}"}
            if not isinstance(data, dict) or data.get("connected") is False or data.get("ok") is False:
                return {"success": False, "error": "DisplayNet DRI0050 nie jest połączony."}
            duty_raw = data.get("duty_raw", 0)
            power_pct = data.get("duty_percent", round(duty_raw * 100.0 / 255.0, 2))
            return {
                "success": True,
                "data": {
                    **data,
                    "power_pct": power_pct,
                    "duty_raw": duty_raw,
                    "enabled": bool(data.get("enabled", data.get("enable", False))),
                    "source": "displaynet",
                },
            }
        elif command == "stop":
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.post(f"{base_url}/api/v1/dri0050", json={"action": "stop"})
                    if resp.status_code == 404:
                        resp = await client.post(f"{base_url}/api/stop")
                    resp.raise_for_status()
                    data = resp.json()
            except Exception as exc:
                return {"success": False, "error": f"DisplayNet DRI0050 stop failed: {exc}"}
            return {"success": True, "stopped": True, "data": data}
        elif command == "set_speed":
            power = params.get("power_pct", params.get("powerPct", 0))
            if isinstance(power, bool):
                return {"success": False, "error": "Moc pompy musi być liczbą 0–100%."}
            try:
                power = float(power)
            except (ValueError, TypeError):
                return {"success": False, "error": "Moc pompy musi być liczbą 0–100%."}
            if not math.isfinite(power) or not 0 <= power <= 100:
                return {"success": False, "error": "Moc pompy musi mieścić się w zakresie 0–100%."}
            if power == 0:
                return await _execute_displaynet_command(device_or_plugin, "stop", {})
            duty_raw = max(1, min(255, int(round(power * 255 / 100))))
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.post(
                        f"{base_url}/api/v1/dri0050",
                        json={"action": "run", "duty_raw": duty_raw},
                    )
                    if resp.status_code == 404:
                        resp = await client.post(f"{base_url}/api/speed", json={"power_pct": power})
                    resp.raise_for_status()
                    data = resp.json()
            except Exception as exc:
                return {"success": False, "error": f"DisplayNet DRI0050 set_speed failed: {exc}"}
            return {"success": True, "power_pct": power, "duty_raw": duty_raw, "data": data}
        else:
            return {"success": False, "error": f"Nieobsługiwane polecenie DisplayNet DRI0050: {command}"}
    else:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                if command == "status":
                    resp = await client.get(f"{base_url}/api/status")
                    resp.raise_for_status()
                    data = resp.json()
                    return {"success": True, "data": {**data, "source": "displaynet"}}
                elif command == "stop":
                    resp = await client.post(f"{base_url}/api/stop")
                    resp.raise_for_status()
                    return {"success": True, "stopped": True, "data": resp.json()}
                elif command == "energize":
                    enable = params.get("enable", True)
                    resp = await client.post(f"{base_url}/api/energize", json={"enable": enable})
                    resp.raise_for_status()
                    return {"success": True, "energized": enable, "data": resp.json()}
                elif command == "move":
                    position = params.get("position", 0)
                    resp = await client.post(f"{base_url}/api/target", json={"position": position})
                    resp.raise_for_status()
                    return {"success": True, "position": position, "data": resp.json()}
                elif command == "reciprocate":
                    resp = await client.post(f"{base_url}/api/reciprocate", json=params)
                    resp.raise_for_status()
                    return {"success": True, "data": resp.json()}
                else:
                    return {"success": False, "error": f"Polecenie {command} nieobsługiwane dla DisplayNet Tic249"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


async def motor_command(plugin, command: str, params: dict) -> dict:
    """Resolve at command time, including commands sent through PluginRegistry."""
    from oqlos.hardware.plugins.stacknet_motor import execute

    async with LOCK:
        try:
            selected = source(MOTOR_DEVICES[plugin.PLUGIN_ID])
        except (OSError, ValueError) as exc:
            if command == "stop":
                # A damaged settings file must never prevent a best-effort
                # stop on either possible owner. Both calls are safe-off only.
                results = await asyncio.gather(
                    plugin._execute_boardnet_command("stop", {"stop_at_limit": False}),
                    execute(MOTOR_DEVICES[plugin.PLUGIN_ID], "stop", {}),
                    _execute_displaynet_command(plugin.PLUGIN_ID, "stop", {}),
                    return_exceptions=True,
                )
                ok = any(isinstance(result, dict) and result.get("success") is True for result in results)
                return {"success": ok, "message" if ok else "error":
                        "Nie można odczytać konfiguracji; wysłano zatrzymanie do kontrolerów."}
            return {"success": False, "error": str(exc)}
        try:
            if selected == "stacknet":
                return await execute(MOTOR_DEVICES[plugin.PLUGIN_ID], command, params)
            if selected == "displaynet":
                return await _execute_displaynet_command(plugin.PLUGIN_ID, command, params)
            if plugin.config.connection_type == "modbus-rtu" and plugin._bus is None:
                if not await plugin.connect():
                    return {"success": False, "error": "Nie można połączyć napędu BoardNet."}
            return await plugin._execute_boardnet_command(command, params)
        except (OSError, ValueError) as exc:
            return {"success": False, "error": str(exc)}

