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


def rig_oql_path() -> Path | None:
    explicit = os.environ.get("OQLOS_RIG_OQL_PATH") or os.environ.get("RIG_OQL_PATH")
    if explicit:
        p = Path(explicit)
        if p.exists() or p.parent.exists():
            return p
    if os.environ.get("OQLOS_CONTROL_SOURCES_PATH"):
        return None
    profile_path = os.environ.get("STACKNET_OQL_PROFILE_PATH")
    if profile_path:
        p = Path(profile_path).parent / "rig.oql"
        if p.exists():
            return p
    candidates = [
        Path("/scenarios/layers/hardware/rig.oql"),
        Path("/home/pi/oqlos/oql-scenario/layers/hardware/rig.oql"),
        Path.home() / "github/oqlos/oql-scenario/layers/hardware/rig.oql",
        Path.home() / "oqlos/oql-scenario/layers/hardware/rig.oql",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _parse_oql_key(text: str, key: str) -> str | None:
    import re
    m = re.search(rf"(?m)^\s*SET\s+['\"]{re.escape(key)}['\"]\s+['\"]([^'\"\r\n]*)['\"]", text)
    return m.group(1).strip() if m else None


def _update_oql_key(text: str, key: str, value: str) -> str:
    import re
    pattern = rf"(?m)^(\s*SET\s+['\"]{re.escape(key)}['\"]\s+)['\"][^'\"\r\n]*['\"]([^\r\n]*)$"
    if re.search(pattern, text):
        return re.sub(pattern, rf"\g<1>'{value}'\2", text)
    m = re.search(r"(?m)^(\s*CONFIG:\s*)$", text)
    if m:
        return re.sub(r"(?m)^(\s*CONFIG:\s*)$", rf"\1\n  SET '{key}' '{value}'", text, count=1)
    return text.rstrip() + f"\n  SET '{key}' '{value}'\n"


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
    oql_file = rig_oql_path()
    if oql_file and oql_file.exists():
        try:
            raw = oql_file.read_bytes()
            text = raw.decode("utf-8")
            pump = _parse_oql_key(text, "rig.pump.host") or DEFAULTS["pump"]
            stepper = (_parse_oql_key(text, "rig.tic249.host")
                       or _parse_oql_key(text, "rig.stepper.host")
                       or DEFAULTS["stepper"])
            valves = _parse_oql_key(text, "rig.valves.host") or DEFAULTS["valves"]
            sources = {"pump": pump, "stepper": stepper, "valves": valves}
            validate(sources)
            return {"sources": sources, "revision": hashlib.sha256(raw).hexdigest()}
        except Exception:
            pass

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
    oql_file = rig_oql_path()
    if oql_file and oql_file.exists():
        text = oql_file.read_text(encoding="utf-8")
        text = _update_oql_key(text, "rig.pump.host", sources["pump"])
        text = _update_oql_key(text, "rig.tic249.host", sources["stepper"])
        text = _update_oql_key(text, "rig.valves.host", sources["valves"])
        if sources["pump"] == "displaynet":
            sidecar = os.environ.get("STACKNET_DRI0050_SIDECAR_URL", "http://192.168.188.212:8203")
            text = _update_oql_key(text, "rig.pump.sidecar_url", sidecar)
            text = _update_oql_key(text, "rig.pump.health_source", "displaynet-dri0050-sidecar")
        elif sources["pump"] == "boardnet":
            text = _update_oql_key(text, "rig.pump.health_source", "boardnet-dri0050")
        elif sources["pump"] == "stacknet":
            text = _update_oql_key(text, "rig.pump.health_source", "stacknet-dri0050")

        oql_file.parent.mkdir(parents=True, exist_ok=True)
        pending_oql = oql_file.with_suffix(".pending")
        try:
            pending_oql.write_text(text, encoding="utf-8")
            pending_oql.replace(oql_file)
        finally:
            pending_oql.unlink(missing_ok=True)

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

