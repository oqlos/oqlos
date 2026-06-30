from __future__ import annotations

import os
from typing import Any

import httpx

from oqlos.hardware.client.errors import HardwareProxyError, is_oqlos_unavailable, oqlos_error_detail
from oqlos.hardware.client.proxy import OqlosHardwareProxy
from oqlos.hardware.client.tic249_rig_direction import RIG_LEFT_ALIASES, apply_rig_direction_to_plugin_params

MOTOR_TIC249_EXTENDED_COMMANDS = {
    "deenergize",
    "disable",
    "energize",
    "emergency_stop",
    "go_home",
    "home",
    "home_forward",
    "home_reverse",
    "limits",
    "lung_start",
    "lung_stop",
    "motor_disable",
    "motor_enable",
    "move",
    "move_relative",
    "position",
    "reciprocating_motion",
    "standby",
    "status",
    "stop",
    "tic249_reciprocate",
    "tic249_cycle",
    "tic249_inhale",
    "tic249_forward",
    "tic249_exhale",
    "tic249_backward",
    "tic249_stop",
}

_PLUGIN_PATH = "/api/v1/plugins/motor-tic249/execute"
_LUNG_DISABLE_PATH = "/api/v1/hardware/lung/disable"
_DISABLE_COMMANDS = frozenset({"motor_disable", "deenergize", "disable", "standby"})
_RECIPROCATE_PLUGIN_COMMAND = "reciprocate"
_DEFAULT_TARGET_VELOCITY = 100_000
_RAW_SPEED_FACTOR = 10_000


def _arg(args: dict[str, Any], snake: str, camel: str | None = None, default: Any = None) -> Any:
    if snake in args:
        return args[snake]
    if camel and camel in args:
        return args[camel]
    return default


def _plugin_payload(command: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"command": command, "params": params or {}}


async def _execute(proxy: OqlosHardwareProxy, command: str, params: dict[str, Any] | None = None) -> Any:
    return await proxy._proxy_oqlos_request("POST", _PLUGIN_PATH, payload=_plugin_payload(command, params))


def _steps_per_second_to_raw(value: Any, args: dict[str, Any]) -> int:
    try:
        steps = float(value)
    except (TypeError, ValueError):
        steps = float(_DEFAULT_TARGET_VELOCITY)
    max_steps = _arg(args, "max_steps_per_second", "maxStepsPerSecond", 1000)
    try:
        steps = min(steps, float(max_steps))
    except (TypeError, ValueError):
        pass
    return int(steps * _RAW_SPEED_FACTOR)


def _normalize_motion_params(args: dict[str, Any]) -> dict[str, Any]:
    params = dict(args)
    speed_unit = _arg(params, "speed_unit", "speedUnit")
    if "speed" in params and speed_unit == "steps/s":
        params["speed"] = _steps_per_second_to_raw(params["speed"], params)
    elif "speed" in params and _arg(params, "max_steps_per_second", "maxStepsPerSecond") is not None:
        params["speed"] = _steps_per_second_to_raw(params["speed"], params)

    acceleration_unit = _arg(params, "acceleration_unit", "accelerationUnit")
    acceleration = _arg(params, "acceleration", "accelerationPercentPerSecond")
    if acceleration is not None:
        try:
            value = float(acceleration)
        except (TypeError, ValueError):
            value = 0.0
        if "accelerationPercentPerSecond" in params and value > 100:
            value = 100
        if acceleration_unit in {"%/s", "percent/s", "percent_per_second"}:
            params["acceleration"] = int(value * 1000)
        elif acceleration_unit in {"pulses/s2", "steps/s2", "steps/s^2"}:
            params["acceleration"] = int(value * 100)
        elif "accelerationPercentPerSecond" in params:
            params["acceleration"] = int(value * 1000)

    for key in (
        "speed_unit",
        "speedUnit",
        "max_steps_per_second",
        "maxStepsPerSecond",
        "acceleration_unit",
        "accelerationUnit",
        "accelerationPercentPerSecond",
        "default_speed_steps_per_second",
        "defaultSpeedStepsPerSecond",
    ):
        params.pop(key, None)
    return params


def _stroke_steps(args: dict[str, Any], default: int = 500) -> int:
    return int(_arg(args, "steps", "strokeSteps", _arg(args, "stroke_steps", "strokeSteps", default)))


def _apply_reciprocate_direction(params: dict[str, Any], args: dict[str, Any]) -> None:
    apply_rig_direction_to_plugin_params(params, args)


def _build_reciprocate_params(args: dict[str, Any], *, default_cycles: int) -> dict[str, Any]:
    """Build plugin `reciprocate` params; preserve limit_mode for physical end switches."""
    pause_raw = _arg(args, "pause")
    if pause_raw is None:
        pause_raw = _arg(args, "tick_seconds", "tickSeconds", 0.0)
    params: dict[str, Any] = {
        "steps": _stroke_steps(args),
        "cycles": int(args.get("cycles", default_cycles)),
        "pause": float(pause_raw or 0.0),
    }
    speed = _arg(args, "speed", None, 1000)
    if speed is not None:
        if _arg(args, "speed_unit", "speedUnit") == "steps/s" or "speed_unit" in args or "speedUnit" in args:
            params["speed"] = _steps_per_second_to_raw(speed, args)
        else:
            params["speed"] = speed

    _apply_reciprocate_direction(params, args)

    limit_mode = _arg(args, "limit_mode", "limitMode")
    if limit_mode is not None:
        params["limit_mode"] = str(limit_mode)

    if _arg(args, "acceleration", "accelerationPercentPerSecond") is not None:
        normalized = _normalize_motion_params(
            {
                "acceleration": _arg(args, "acceleration", "accelerationPercentPerSecond"),
                "acceleration_unit": _arg(args, "acceleration_unit", "accelerationUnit"),
            }
        )
        if normalized.get("acceleration") is not None:
            params["acceleration"] = normalized["acceleration"]

    return params


def _map_lung_or_reciprocate(command: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    default_cycles = 1_000_000 if command == "reciprocating_motion" else 3
    merged = dict(args)
    if command == "reciprocating_motion" and _arg(merged, "speed_unit", "speedUnit") is None:
        merged.setdefault("speed_unit", "steps/s")
    if command == "lung_start":
        # Default lung motion when omitted: 1000 steps/s (raw 10_000_000)
        # and 0.5 s pause between strokes. Explicit speed/pause wins.
        if _arg(merged, "speed") is None:
            merged["speed"] = 1000
            merged.setdefault("speed_unit", "steps/s")
        if _arg(merged, "pause") is None and _arg(merged, "tick_seconds", "tickSeconds") is None:
            merged["pause"] = 0.5
    return "reciprocate", _build_reciprocate_params(merged, default_cycles=default_cycles)


def _command_mapping(command: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if command in {"tic249_inhale", "tic249_forward"}:
        return "move", _normalize_motion_params({"position": _stroke_steps(args), **dict(args)})
    if command in {"tic249_exhale", "tic249_backward"}:
        return "move", _normalize_motion_params({"position": 0, **dict(args)})
    if command in {"tic249_cycle", "tic249_reciprocate"}:
        return "reciprocate", _build_reciprocate_params(args, default_cycles=3)
    if command == "tic249_stop":
        return "stop", {}
    if command in {"deenergize", "disable", "motor_disable", "standby"}:
        return "energize", {"enable": False}
    if command in {"energize", "motor_enable"}:
        return "energize", {"enable": True}
    if command in {"status", "limits", "position"}:
        return "status", {}
    if command in {"stop", "emergency_stop", "lung_stop"}:
        return "stop", {}
    if command in {"home", "home_reverse", "go_home"}:
        return "home", {"direction": "reverse", **dict(args)}
    if command == "home_forward":
        return "home", {"direction": "forward", **dict(args)}
    if command == "move":
        return "move", _normalize_motion_params({"position": 0, **dict(args)})
    if command in {"lung_start", "reciprocating_motion"}:
        return _map_lung_or_reciprocate(command, args)
    return command, dict(args)


def _extract_position(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    data = payload.get("data")
    if isinstance(data, dict) and "position" in data:
        return int(data["position"])
    if "position" in payload:
        return int(payload["position"])
    return 0


def _command_error_message(result: dict[str, Any]) -> str | None:
    """Collect the best available error string from plugin or sidecar payloads."""
    for key in ("error", "message", "detail"):
        value = result.get(key)
        if value not in (None, ""):
            return str(value)

    data = result.get("data")
    if isinstance(data, dict):
        for key in ("error", "message", "detail"):
            value = data.get(key)
            if value not in (None, ""):
                return str(value)
        if data.get("connected") is False:
            return str(data.get("error") or "Tic249 motor is not connected")

    nested_ok = result.get("ok")
    if isinstance(nested_ok, dict):
        for key in ("error", "message", "detail"):
            value = nested_ok.get(key)
            if value not in (None, ""):
                return str(value)
        if nested_ok.get("success") is False:
            return _command_error_message(nested_ok)

    base_url = result.get("base_url")
    path = result.get("path")
    if base_url and path:
        return f"Tic249 command failed ({base_url}{path})"
    return None


def _generic_failure_hint(result: dict[str, Any]) -> str:
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    hints: list[str] = []
    for key in ("connected", "status", "energized", "error", "message"):
        if key in result and result[key] not in (None, ""):
            hints.append(f"{key}={result[key]!r}")
        elif key in data and data[key] not in (None, ""):
            hints.append(f"{key}={data[key]!r}")
    if hints:
        return f"Tic249 de-energize failed ({', '.join(hints)})"
    return (
        "Tic249 de-energize failed (no detail from plugin; "
        "check motor-tic249 health, Tic sidecar, and USB device)"
    )


def _failure(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    if result.get("idempotent_success"):
        return None
    if result.get("success") is False or result.get("ok") is False:
        return _command_error_message(result) or _generic_failure_hint(result)
    data = result.get("data")
    if isinstance(data, dict) and data.get("success") is False:
        return _command_error_message(data) or _command_error_message(result) or _generic_failure_hint(result)
    return None


def _plugin_unavailable_error(exc: HardwareProxyError) -> bool:
    if exc.status_code == 404:
        return True
    detail = exc.detail
    if isinstance(detail, str):
        text = detail
    elif isinstance(detail, dict):
        text = str(
            detail.get("error")
            or detail.get("message")
            or detail.get("detail")
            or (detail.get("response") or {}).get("detail")
            or ""
        )
    else:
        text = str(detail or "")
    return "no active instance" in text.lower()


def _tic249_sidecar_base_urls() -> list[str]:
    """Candidate Tic sidecar bases (host, container, and explicit env)."""
    seen: set[str] = set()
    urls: list[str] = []
    for raw in (
        os.getenv("TIC249_DIRECT_API_BASE"),
        os.getenv("OQLOS_LUNG_MOTOR_URL"),
        os.getenv("LUNG_MOTOR_URL"),
        os.getenv("TIC249_URL"),
        "http://hw-tic249:5000",
        "http://127.0.0.1:8205",
        "http://localhost:8205",
        "http://host.docker.internal:8205",
    ):
        if not raw:
            continue
        base = str(raw).rstrip("/")
        if base in seen:
            continue
        seen.add(base)
        urls.append(base)
    return urls or ["http://127.0.0.1:8205"]


def _tic249_sidecar_base_url() -> str:
    return _tic249_sidecar_base_urls()[0]


async def _sidecar_reports_deenergized() -> bool:
    async with httpx.AsyncClient(timeout=3.0) as client:
        for base in _tic249_sidecar_base_urls():
            try:
                resp = await client.get(f"{base}/api/status")
            except Exception:
                continue
            if resp.status_code >= 300:
                continue
            payload = resp.json() if resp.content else {}
            if isinstance(payload, dict) and payload.get("energized") is False:
                return True
    return False


async def _attempt_disable_deenergize(
    hardware_proxy: OqlosHardwareProxy,
    command: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Sidecar and lung/disable paths do not require an OqlOS plugin registry instance."""
    for fallback_name, attempt in (
        ("tic249_sidecar_energize", lambda: _direct_sidecar_deenergize(command)),
        ("lung_disable", lambda: _lung_disable_fallback(hardware_proxy, command)),
    ):
        result = await attempt()
        if result is not None:
            return result, fallback_name
    if await _sidecar_reports_deenergized():
        return (
            {
                "success": True,
                "status": "de-energized",
                "idempotent_success": True,
                "fallback": "tic249_sidecar_status",
            },
            "tic249_sidecar_status",
        )
    return None, None


def _disable_success_response(
    command: str,
    fallback_result: dict[str, Any],
    fallback_name: str,
) -> dict[str, Any]:
    if fallback_name == "lung_disable":
        target_path = _LUNG_DISABLE_PATH
        target_params: dict[str, Any] = {}
    elif fallback_name == "tic249_sidecar_status":
        target_path = f"{_tic249_sidecar_base_url()}/api/status"
        target_params = {}
    else:
        target_path = f"{_tic249_sidecar_base_url()}/api/energize"
        target_params = {"enable": False}
    return {
        "ok": True,
        "peripheral_id": "motor-tic249",
        "command": command,
        "target": {"method": "POST", "path": target_path, "params": target_params},
        "result": fallback_result,
        "note": f"De-energize via {fallback_name} (plugin registry not required)",
    }


def _sidecar_reciprocate_preferred() -> bool:
    """Prefer hw-tic249 /api/reciprocate (real limit switches) over OqlOS plugin mock."""
    return os.getenv("TIC249_RECIPROCATE_VIA_SIDECAR", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


async def _attempt_reciprocate_via_sidecar(params: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """POST /api/reciprocate on Tic249 sidecar (rpi-motor-tic249 web_panel)."""
    payload = {
        k: v
        for k, v in params.items()
        if k
        in {
            "steps",
            "speed",
            "cycles",
            "pause",
            "direction",
            "start_direction",
            "limit_mode",
            "acceleration",
        }
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(8.0)) as client:
        for base in _tic249_sidecar_base_urls():
            try:
                resp = await client.post(f"{base}/api/reciprocate", json=payload)
            except Exception:
                continue
            if resp.status_code >= 300:
                continue
            body = resp.json() if resp.content else {}
            if not isinstance(body, dict):
                continue
            if body.get("success") is False:
                continue
            return {**body, "success": True, "fallback": "tic249_sidecar_reciprocate", "base_url": base}, base
    return None, None


async def _direct_sidecar_deenergize(command: str) -> dict[str, Any] | None:
    """De-energize via Tic sidecar when OqlOS plugin registry has no active instance."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        for base in _tic249_sidecar_base_urls():
            try:
                resp = await client.post(f"{base}/api/energize", json={"enable": False})
            except Exception:
                continue
            if resp.status_code >= 300:
                continue
            payload = resp.json() if resp.content else {}
            if not isinstance(payload, dict):
                continue
            normalized = _normalize_target_state(command, {**payload, "success": True, "data": payload})
            if _failure(normalized) is not None:
                continue
            return {**normalized, "fallback": "tic249_sidecar_energize", "base_url": base}
    return None


async def _lung_disable_fallback(
    hardware_proxy: OqlosHardwareProxy,
    command: str,
) -> dict[str, Any] | None:
    """Retry de-energize through the lung/disable route when plugin execute fails."""
    try:
        result = await hardware_proxy._proxy_oqlos_request("POST", _LUNG_DISABLE_PATH, payload=None)
    except HardwareProxyError:
        return None
    if not isinstance(result, dict):
        return None
    normalized = _normalize_target_state(command, result)
    if _failure(normalized) is not None:
        return None
    return {**normalized, "fallback": "lung_disable"}


def _normalize_target_state(command: str, result: Any) -> Any:
    if not isinstance(result, dict):
        return result
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    status = str(result.get("status") or data.get("status") or "").lower()
    disable_commands = {"motor_disable", "deenergize", "disable", "standby"}
    stop_commands = {"lung_stop", "stop", "emergency_stop"}
    already_deenergized = status in {"de-energized", "disabled"} or data.get("energized") is False
    already_stopped = status in {"stopped", "idle"}
    if command in disable_commands and already_deenergized and not result.get("error"):
        return {**result, "ok": True, "success": True, "idempotent_success": True}
    if command in stop_commands and already_stopped and not result.get("error"):
        return {**result, "ok": True, "success": True, "idempotent_success": True}
    return result


async def _handle_hardware_proxy_error(
    hardware_proxy: OqlosHardwareProxy,
    command: str,
    plugin_command: str,
    params: dict[str, Any],
    exc: HardwareProxyError,
) -> dict[str, Any] | None:
    if command in _DISABLE_COMMANDS and _plugin_unavailable_error(exc):
        fallback_result, fallback_name = await _attempt_disable_deenergize(hardware_proxy, command)
        if fallback_result is not None and fallback_name is not None:
            return _disable_success_response(command, fallback_result, fallback_name)
        message, detail = oqlos_error_detail(exc)
        return {
            "ok": False,
            "peripheral_id": "motor-tic249",
            "command": command,
            "target": {"method": "POST", "path": _PLUGIN_PATH, "params": _plugin_payload(plugin_command, params)},
            "error": (
                "Cannot de-energize Tic T249: plugin not active and sidecar/lung fallbacks failed. "
                f"{message}"
            ),
            "hint": (
                "Ensure hw-tic249 is running (e.g. port 8205) and set OQLOS_LUNG_MOTOR_URL / TIC249_URL "
                "to a reachable base URL from connect-scenario-backend"
            ),
            "result": {"success": False, "error": message, "detail": detail},
        }
    if command == "status" and _plugin_unavailable_error(exc):
        return {
            "ok": True,
            "optional": True,
            "peripheral_id": "motor-tic249",
            "command": command,
            "target": {"method": "POST", "path": _PLUGIN_PATH, "params": _plugin_payload(plugin_command, params)},
            "note": "motor-tic249 plugin disabled (bench Modbus-only); status step treated as skipped",
            "result": {"status": "disabled", "success": True, "idempotent_success": True},
        }
    if not is_oqlos_unavailable(exc):
        return None
    message, detail = oqlos_error_detail(exc)
    return {
        "ok": False,
        "peripheral_id": "motor-tic249",
        "command": command,
        "target": {"method": "POST", "path": _PLUGIN_PATH, "params": _plugin_payload(plugin_command, params)},
        "error": message,
        "result": {"success": False, "error": message, "detail": detail},
    }


async def _handle_move_relative_command(
    hardware_proxy: "OqlosHardwareProxy", command_args: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Resolve move_relative into absolute position params; return (plugin_command, params)."""
    status = await _execute(hardware_proxy, "status", {})
    current = _extract_position(status)
    offset = command_args.get("offset")
    if offset is None:
        steps = abs(int(command_args.get("steps", 0)))
        direction = str(command_args.get("direction", "right")).lower()
        offset = -steps if direction in RIG_LEFT_ALIASES else steps
    raw_params = {**command_args, "offset": int(offset), "position": current + int(offset)}
    raw_params.pop("direction", None)
    raw_params.pop("steps", None)
    params = _normalize_motion_params(raw_params)
    params["relative_from"] = current
    params["offset"] = int(offset)
    return "move", params


async def run_extended_motor_tic249_command(
    hardware_proxy: OqlosHardwareProxy,
    command: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    command_args = args or {}
    plugin_command, params = _command_mapping(command, command_args)

    if command == "move_relative":
        plugin_command, params = await _handle_move_relative_command(hardware_proxy, command_args)

    if command in _DISABLE_COMMANDS:
        fallback_result, fallback_name = await _attempt_disable_deenergize(hardware_proxy, command)
        if fallback_result is not None and fallback_name is not None:
            return _disable_success_response(command, fallback_result, fallback_name)

    if plugin_command == _RECIPROCATE_PLUGIN_COMMAND and _sidecar_reciprocate_preferred():
        sidecar_result, sidecar_base = await _attempt_reciprocate_via_sidecar(params)
        if sidecar_result is not None and sidecar_base is not None:
            return {
                "ok": True,
                "peripheral_id": "motor-tic249",
                "command": command,
                "target": {"method": "POST", "path": f"{sidecar_base}/api/reciprocate", "params": params},
                "result": sidecar_result,
                "note": "Reciprocate via Tic249 sidecar (physical limit switches; set TIC249_RECIPROCATE_VIA_SIDECAR=0 to use OqlOS plugin only)",
            }

    try:
        result = await _execute(hardware_proxy, plugin_command, params)
    except HardwareProxyError as exc:
        error_response = await _handle_hardware_proxy_error(hardware_proxy, command, plugin_command, params, exc)
        if error_response is not None:
            return error_response
        raise

    result = _normalize_target_state(command, result)
    failure = _failure(result)
    if failure and command in _DISABLE_COMMANDS:
        fallback_result, fallback_name = await _attempt_disable_deenergize(hardware_proxy, command)
        if fallback_result is not None and fallback_name is not None:
            return _disable_success_response(command, fallback_result, fallback_name)
    return {
        "ok": failure is None,
        "peripheral_id": "motor-tic249",
        "command": command,
        "target": {"method": "POST", "path": _PLUGIN_PATH, "params": _plugin_payload(plugin_command, params)},
        **({"error": failure} if failure else {}),
        "result": result,
    }
