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


def validate(sources: dict[str, str]) -> None:
    if set(sources) != set(DEFAULTS):
        raise ValueError("Wymagane są ustawienia pompy, silnika krokowego i zaworów.")
    for key, value in sources.items():
        allowed = {"boardnet", "stacknet", "auto"} if key == "valves" else {"boardnet", "stacknet"}
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
                    return_exceptions=True,
                )
                ok = all(isinstance(result, dict) and result.get("success") is True for result in results)
                return {"success": ok, "message" if ok else "error":
                        "Nie można odczytać konfiguracji; wysłano zatrzymanie do obu kontrolerów."}
            return {"success": False, "error": str(exc)}
        try:
            if selected == "stacknet":
                return await execute(MOTOR_DEVICES[plugin.PLUGIN_ID], command, params)
            if plugin.config.connection_type == "modbus-rtu" and plugin._bus is None:
                if not await plugin.connect():
                    return {"success": False, "error": "Nie można połączyć napędu BoardNet."}
            return await plugin._execute_boardnet_command(command, params)
        except (OSError, ValueError) as exc:
            return {"success": False, "error": str(exc)}
