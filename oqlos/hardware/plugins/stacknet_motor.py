"""Adapt the existing StackNet DRI0050/Tic APIs without changing firmware auth.

StackNet currently exposes direct Tic commands, not the BoardNet sidecar's
reciprocation or stroke-sequence engine. Unsupported commands fail explicitly.
"""
from __future__ import annotations

import math
import os

import httpx

PATHS = {"pump": "/api/v1/dri0050", "stepper": "/api/v1/motor"}


async def request(device: str, body: dict | None = None) -> dict:
    token = os.environ.get("STACKNET_OQL_TOKEN", "")
    if body is not None and not token:
        raise ValueError("Brak poświadczeń sterowania silnikiem StackNet (STACKNET_OQL_TOKEN).")
    url = os.environ.get("STACKNET_RUNTIME_URL", "http://stacknet.local:8080").rstrip("/")
    headers = {"X-OQL-Token": token} if token else {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.request(
            "POST" if body is not None else "GET", url + PATHS[device],
            headers=headers, **({"json": body} if body is not None else {}),
        )
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict) or data.get("error") or data.get("ok") is False or data.get("connected") is False:
        raise ValueError("StackNet nie potwierdził dostępności urządzenia lub wykonania polecenia.")
    if body is not None and (data.get("ok") is not True if device == "stepper" else data.get("connected") is not True):
        raise ValueError("StackNet nie potwierdził wykonania polecenia.")
    return data


async def status(device: str) -> dict:
    data = await request(device)
    if data.get("connected") is not True:
        raise ValueError("StackNet nie potwierdził połączenia urządzenia.")
    if device == "pump":
        return {**data, "power_pct": data.get("duty_percent"), "pwm_value": data.get("duty_raw")}
    return {**data, "position": data.get("current_position")}


async def execute(device: str, command: str, params: dict) -> dict:
    try:
        if command == "status":
            return {"success": True, "data": await status(device)}
        if device == "pump":
            if command == "stop":
                data = await request(device, {"action": "stop"})
            elif command == "set_speed":
                power = params.get("power_pct", params.get("powerPct", 0))
                if isinstance(power, bool):
                    raise ValueError("Moc pompy musi być liczbą 0–100%.")
                power = float(power)
                if not math.isfinite(power) or not 0 <= power <= 100:
                    raise ValueError("Moc pompy musi mieścić się w zakresie 0–100%.")
                if power == 0:
                    data = await request(device, {"action": "stop"})
                else:
                    await request(device, {"action": "set_duty", "duty_raw": round(power * 255 / 100)})
                    try:
                        data = await request(device, {"action": "enable"})
                    except (httpx.HTTPError, ValueError):
                        await request(device, {"action": "stop"})
                        raise
            else:
                raise ValueError("Polecenie pompy nie jest obsługiwane przez StackNet.")
            data = {**data, "power_pct": data.get("duty_percent"), "pwm_value": data.get("duty_raw")}
        elif command == "stop":
            if params.get("stop_mode") == "reach_limit" or params.get("stop_at_limit"):
                raise ValueError("StackNet obsługuje zatrzymanie natychmiastowe; dojazd do krańcówki wymaga BoardNet.")
            await request(device, {"action": "halt"})
            data = await request(device, {"action": "deenergize"})
            data = {**data, "stopped": True, "energized": False}
        elif command == "energize":
            enable = params.get("enable", True)
            if type(enable) is not bool:
                raise ValueError("enable musi być wartością logiczną.")
            data = await request(device, {"action": "energize" if enable else "deenergize"})
            data = {**data, "energized": enable}
        elif command == "move":
            position = params.get("position", 0)
            if type(position) is not int or not -(2**31) <= position < 2**31:
                raise ValueError("Pozycja silnika musi być 32-bitową liczbą całkowitą.")
            if "speed" in params:
                raise ValueError("StackNet używa prędkości zapisanej w Tic; zmiana prędkości ruchu wymaga BoardNet.")
            data = await request(device, {"action": "set_target_position", "position": position})
            data = {**data, "position": position}
        else:
            raise ValueError("StackNet nie obsługuje cykli sztucznego płuca ani sekwencji skoków. Wybierz BoardNet.")
        return {"success": True, "data": data}
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        message = str(exc) if not isinstance(exc, httpx.HTTPError) else "Błąd połączenia lub autoryzacji silnika StackNet."
        return {"success": False, "error": message}
