"""Controller selection; switching requires idle devices on the current controller."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StrictStr

from oqlos.hardware import control_sources as store

router = APIRouter(prefix="/control-sources", tags=["control-sources"])


class ControlSourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: dict[str, StrictStr]
    revision: StrictStr


def read_settings() -> dict:
    try:
        return store.snapshot()
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Nie można odczytać konfiguracji sterowania.") from exc


@router.get("")
async def get_sources() -> dict:
    async with store.LOCK:
        return read_settings()


async def ensure_idle(device: str, selections: set[str]) -> None:
    from oqlos.api.hardware_gateway import get_hardware_gateway
    from oqlos.hardware.plugins.stacknet_motor import execute

    gateway = get_hardware_gateway()
    if not gateway.is_real:
        return
    if device == "valves":
        controllers = set()
        for selection in selections:
            controllers.update(
                gateway.valve_controllers() if selection == "auto" else
                ["modbus-io" if selection == "boardnet" else "io-m5-4in8out"]
            )
        if not controllers:
            raise HTTPException(503, "Brak skonfigurowanych kontrolerów zaworów.")
        checked = 0
        for plugin_id in controllers:
            plugin = await gateway._get_or_connect_plugin(plugin_id)
            if plugin is None:
                continue
            result = await plugin.execute_command("read_io_snapshot", {})
            coils = result.get("data", {}).get("coils")
            if result.get("success") is not True or not isinstance(coils, list) or not coils:
                raise HTTPException(503, "Nie można potwierdzić wyłączenia wyjść zaworów.")
            if any(type(value) is not bool for value in coils):
                raise HTTPException(503, "Nieprawidłowy odczyt stanu zaworów.")
            if any(coils):
                raise HTTPException(409, "Wyłącz zawory przed zmianą kontrolera.")
            checked += 1
        if not checked:
            raise HTTPException(503, "Nie można potwierdzić wyłączenia bieżącego kontrolera zaworów.")
        return
    for selection in selections:
        if selection == "stacknet":
            result = await execute(device, "status", {})
        else:
            plugin_id = "motor-dri0050" if device == "pump" else "motor-tic249"
            plugin = await gateway._get_or_connect_plugin(plugin_id)
            if plugin and plugin.config.connection_type == "http" and plugin._client:
                # Inspect raw status: legacy presentation adapters fill missing
                # power fields with zero, which is not proof of an idle motor.
                import httpx
                try:
                    response = await plugin._client.get(plugin._base_url + "/api/status")
                    response.raise_for_status()
                    raw = response.json()
                    result = {"success": isinstance(raw, dict) and raw.get("success") is not False, "data": raw}
                except (httpx.HTTPError, ValueError) as exc:
                    raise HTTPException(503, "Nie można odczytać stanu urządzenia BoardNet.") from exc
            else:
                result = await plugin._execute_boardnet_command("status", {}) if plugin else {}
        data = result.get("data", {})
        if result.get("success") is not True or not isinstance(data, dict) or data.get("connected") is False:
            raise HTTPException(503, "Nie można potwierdzić zatrzymania urządzenia na bieżącym kontrolerze.")
        if device == "pump":
            powers = [data[key] for key in ("power_pct", "duty_percent", "duty", "duty_raw", "pwm_value") if key in data]
            idle = bool(powers) and all(type(power) in (int, float) and power == 0 for power in powers) and data.get("enabled") is not True
        else:
            idle = (
                data.get("energized") is False
                and data.get("current_velocity", data.get("velocity", 0)) == 0
                and not any(data.get(key) for key in ("reciprocating_active", "homing_active", "running"))
            )
        if not idle:
            raise HTTPException(409, "Zatrzymaj pompę i wyłącz napęd silnika przed zmianą kontrolera.")


@router.put("")
async def update_sources(payload: ControlSourceUpdate) -> dict:
    try:
        store.validate(payload.sources)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    async with store.LOCK:
        current = read_settings()
        if payload.revision != current["revision"]:
            raise HTTPException(409, "Ustawienia zmieniły się. Odśwież formularz.")
        for device, selection in payload.sources.items():
            if selection != current["sources"][device]:
                # Selecting a destination must be possible before physically
                # moving its cable. Only the current owner must be idle; the
                # destination is checked by its normal command/health path.
                await ensure_idle(device, {current["sources"][device]})
        if payload.sources == current["sources"]:
            return current
        try:
            return store.save(payload.sources)
        except OSError as exc:
            raise HTTPException(503, "Nie udało się zapisać konfiguracji sterowania.") from exc
