"""OqlOS hardware control proxy used by UI/backend clients.

This module owns the command mapping and OqlOS API proxy behavior. Applications
such as c2004 should expose their own HTTP routes or UI, but keep hardware
control semantics here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

import httpx

from oqlos.hardware.tic249_units import TIC249_DEFAULT_TARGET_VELOCITY


_DEFAULT_OQLOS_API_BASE = "http://host.docker.internal:8202"

PERIPHERAL_STATUS_COMMANDS: dict[str, str] = {
    "modbus-io": "health",
    "motor-dri0050": "status",
    "motor-tic249": "status",
    "modbus-adc": "read_sensor",
    "piadc": "read_sensor",
}

FALLBACK_ADAPTERS: list[dict[str, str]] = [
    {
        "id": "modbus-adc",
        "name": "Waveshare Modbus RTU Analog Input 8CH",
        "protocol": "Modbus RTU (RS485)",
    },
    {
        "id": "motor-tic249",
        "name": "Pololu Tic T249",
        "protocol": "USB + REST",
    },
    {
        "id": "motor-dri0050",
        "name": "DFRobot DRI0050",
        "protocol": "MODBUS RTU (serial)",
    },
    {
        "id": "modbus-io",
        "name": "Waveshare Modbus RTU IO 8CH",
        "protocol": "Modbus RTU (RS485)",
    },
]

MODBUS_ALLOWED_VALVE_IDS = {
    *(f"valve-{idx}" for idx in range(1, 15)),
    "valve-nc",
    "valve-sc",
    "valve-wc",
}


def _float_from_env(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def candidate_oqlos_bases(api_base: str) -> list[str]:
    """Return the configured OqlOS base URL plus the common 8200/8202 fallback."""
    configured = (api_base or _DEFAULT_OQLOS_API_BASE).rstrip("/")
    candidates = [configured]
    if configured.endswith(":8202"):
        candidates.append(configured[:-5] + ":8200")
    elif configured.endswith(":8200"):
        candidates.append(configured[:-5] + ":8202")

    deduped: list[str] = []
    for item in candidates:
        if item not in deduped:
            deduped.append(item)
    return deduped


@dataclass(frozen=True)
class OqlosHardwareProxyConfig:
    api_base: str = _DEFAULT_OQLOS_API_BASE
    timeout_seconds: float = 45.0
    identify_timeout_seconds: float | None = None
    connect_timeout_seconds: float = 2.0
    proxy_prefix: str = "/api/v3/hardware"

    def __post_init__(self) -> None:
        object.__setattr__(self, "api_base", (self.api_base or _DEFAULT_OQLOS_API_BASE).rstrip("/"))
        if self.identify_timeout_seconds is None:
            object.__setattr__(self, "identify_timeout_seconds", self.timeout_seconds)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        proxy_prefix: str = "/api/v3/hardware",
    ) -> "OqlosHardwareProxyConfig":
        values = env or os.environ
        timeout = _float_from_env(values, "OQLOS_API_TIMEOUT_SECONDS", 45.0)
        return cls(
            api_base=values.get("OQLOS_API_URL", _DEFAULT_OQLOS_API_BASE),
            timeout_seconds=timeout,
            identify_timeout_seconds=_float_from_env(values, "OQLOS_API_IDENTIFY_TIMEOUT_SECONDS", timeout),
            connect_timeout_seconds=_float_from_env(values, "OQLOS_CONNECT_TIMEOUT_SECONDS", 2.0),
            proxy_prefix=proxy_prefix,
        )


class HardwareProxyError(Exception):
    """Error raised by the OqlOS hardware proxy layer."""

    def __init__(self, status_code: int, detail: Any):
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


def is_oqlos_unavailable(exc: HardwareProxyError) -> bool:
    return exc.status_code in {502, 503, 504}


def oqlos_error_detail(exc: HardwareProxyError) -> tuple[str, Any]:
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("error") or detail.get("message") or detail.get("detail")
        return str(message or "OqlOS API unavailable"), detail
    if detail:
        return str(detail), detail
    return "OqlOS API unavailable", None


def _safe_response_payload(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        text = response.text
        return text if text else None


def _response_error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("error") or payload.get("message")
        if isinstance(detail, dict):
            return str(detail.get("error") or detail.get("message") or detail)
        if detail:
            return str(detail)
    if isinstance(payload, str) and payload:
        return payload
    return ""


class OqlosHardwareProxy:
    """Proxy and command mapper for runtime hardware control via OqlOS."""

    def __init__(
        self,
        config: OqlosHardwareProxyConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config or OqlosHardwareProxyConfig.from_env()
        self._client: httpx.AsyncClient | None = client

    def candidate_bases(self) -> list[str]:
        return candidate_oqlos_bases(self.config.api_base)

    def proxy_info(self) -> dict[str, Any]:
        return {
            "oqlos_api_base": self.config.api_base,
            "oqlos_api_candidates": self.candidate_bases(),
            "oqlos_api_timeout_seconds": self.config.timeout_seconds,
            "oqlos_api_identify_timeout_seconds": self.config.identify_timeout_seconds,
            "proxy_prefix": self.config.proxy_prefix,
        }

    async def close(self) -> None:
        if self._client is not None and not getattr(self._client, "is_closed", False):
            await self._client.aclose()

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or getattr(self._client, "is_closed", False):
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout_seconds, connect=self.config.connect_timeout_seconds),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def _proxy_oqlos(self, path: str, *, timeout: float | None = None) -> dict[str, Any]:
        return await self._proxy_oqlos_request("GET", path, timeout=timeout)

    async def _proxy_oqlos_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        normalized_path = path if path.startswith("/") else f"/{path}"
        req_timeout = httpx.Timeout(
            timeout if timeout is not None else self.config.timeout_seconds,
            connect=self.config.connect_timeout_seconds,
        )
        client = self._get_client()
        targets = [f"{base}{normalized_path}" for base in self.candidate_bases()]
        last_error: httpx.HTTPError | None = None

        for target in targets:
            try:
                res = await client.request(method, target, params=params, json=payload, timeout=req_timeout)
                res.raise_for_status()
                return res.json()
            except httpx.HTTPStatusError as exc:
                response_payload = _safe_response_payload(exc.response)
                response_detail = _response_error_message(response_payload)
                raise HardwareProxyError(
                    exc.response.status_code,
                    {
                        "error": response_detail
                        or f"OqlOS API returned {exc.response.status_code} for {normalized_path}",
                        "status_code": exc.response.status_code,
                        "path": normalized_path,
                        "response": response_payload,
                    },
                ) from exc
            except httpx.HTTPError as exc:
                last_error = exc

        raise HardwareProxyError(
            502,
            {
                "error": f"Cannot reach OqlOS API for {normalized_path}",
                "attempted_targets": targets,
                "last_error": str(last_error) if last_error else "unknown error",
                "timeout_seconds": timeout if timeout is not None else self.config.timeout_seconds,
            },
        )

    async def health(self) -> dict[str, Any]:
        path = "/api/v1/hardware/health"
        try:
            return await self._proxy_oqlos(path, timeout=self.config.timeout_seconds)
        except HardwareProxyError as exc:
            if is_oqlos_unavailable(exc):
                return self._unavailable_health_payload(exc, path)
            raise

    async def identify(self) -> dict[str, Any]:
        try:
            return await self._proxy_oqlos(
                "/api/v1/hardware/identify",
                timeout=self.config.identify_timeout_seconds,
            )
        except HardwareProxyError as exc:
            if is_oqlos_unavailable(exc):
                return self._unavailable_identify_payload(exc)
            raise

    async def peripheral_status(self, peripheral_id: str) -> dict[str, Any]:
        peripheral = peripheral_id.strip().lower()
        if peripheral not in PERIPHERAL_STATUS_COMMANDS:
            return {
                "ok": False,
                "peripheral_id": peripheral,
                "error": "Runtime status is not available for this peripheral",
            }

        command = PERIPHERAL_STATUS_COMMANDS[peripheral]
        try:
            command, result, ok = await self._load_peripheral_status(peripheral)
        except HardwareProxyError as exc:
            return self._unavailable_peripheral_payload(peripheral, command, exc)

        response: dict[str, Any] = {
            "ok": ok,
            "peripheral_id": peripheral,
            "command": command,
            "result": result,
        }
        if not ok and isinstance(result, dict) and result.get("error"):
            response["error"] = result.get("error")
        return response

    async def diagnostic_command(
        self,
        peripheral_id: str,
        command_name: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        peripheral = peripheral_id.strip().lower()
        command = command_name.strip().lower()
        command_args = args or {}

        method, path, params = resolve_diagnostic_target(peripheral, command, command_args)
        try:
            method, path, params, result = await self._execute_diagnostic_command(
                peripheral,
                command,
                method,
                path,
                params,
            )
        except HardwareProxyError as exc:
            if is_oqlos_unavailable(exc):
                return self._unavailable_command_payload(peripheral, command, method, path, params, exc)
            raise

        failure = extract_command_failure(result)
        return {
            "ok": failure is None,
            "peripheral_id": peripheral,
            "command": command,
            "target": {
                "method": method,
                "path": path,
                "params": params or {},
            },
            **({"error": failure} if failure else {}),
            "result": result,
        }

    async def _load_peripheral_status(self, peripheral: str) -> tuple[str, Any, bool]:
        command = PERIPHERAL_STATUS_COMMANDS[peripheral]
        if peripheral == "modbus-io":
            result = await self._proxy_oqlos_request("GET", f"/api/v1/plugins/{peripheral}/health")
            return command, result, bool(result.get("compatible")) if isinstance(result, dict) else False

        if peripheral in {"modbus-adc", "piadc"}:
            result = await self._proxy_oqlos_request("GET", "/api/v1/hardware/sensor/ai01")
            ok = not (isinstance(result, dict) and result.get("success") is False)
            return command, result, ok

        result = await self._proxy_oqlos_request(
            "POST",
            f"/api/v1/plugins/{peripheral}/execute",
            payload={"command": command, "params": {}},
        )
        ok = not (isinstance(result, dict) and result.get("success") is False)
        return command, result, ok

    async def _execute_diagnostic_command(
        self,
        peripheral: str,
        command: str,
        method: str,
        path: str,
        params: dict[str, Any] | None,
    ) -> tuple[str, str, dict[str, Any] | None, Any]:
        if peripheral == "motor-tic249" and command == "motor_disable":
            try:
                result = await self._proxy_oqlos_request(method, path, params=params)
                return method, path, params, result
            except HardwareProxyError as exc:
                if exc.status_code != 404:
                    raise
                fallback_method = "POST"
                fallback_path = "/api/v1/hardware/lung/stop"
                result = await self._proxy_oqlos_request(fallback_method, fallback_path, params=params)
                result = {
                    **(result if isinstance(result, dict) else {"result": result}),
                    "note": "Fallback to /api/v1/hardware/lung/stop (disable endpoint not available)",
                }
                return fallback_method, fallback_path, params, result

        result = await self._proxy_oqlos_request(method, path, params=params)
        return method, path, params, result

    def _unavailable_health_payload(self, exc: HardwareProxyError, path: str) -> dict[str, Any]:
        message, detail = oqlos_error_detail(exc)
        return {
            "status": "unavailable",
            "ok": False,
            "mode": "unavailable",
            "error": message,
            "detail": detail,
            "proxy": {
                "path": path,
                "oqlos_api_base": self.config.api_base,
                "oqlos_api_candidates": self.candidate_bases(),
            },
        }

    def _unavailable_identify_payload(self, exc: HardwareProxyError) -> dict[str, Any]:
        health = self._unavailable_health_payload(exc, "/api/v1/hardware/identify")
        adapters = [
            {
                **adapter,
                "status": "no-access",
                "probe": {
                    "connected": False,
                    "source": "oqlos.hardware.control_proxy",
                    "error": health["error"],
                    "detail": health["detail"],
                },
            }
            for adapter in FALLBACK_ADAPTERS
        ]
        return {
            "mode": "unavailable",
            "platform": {
                "detected": "unknown",
                "selected": "unknown",
                "analog_input_driver_role": "unknown",
                "modbus_adc_driver_role": "unknown",
                "modbus_adc_local_probe_allowed": False,
            },
            "detected": 0,
            "total": len(adapters),
            "adapters": adapters,
            "diagnostics": {
                "health": health,
                "scan_mode": "proxy",
                "scan_performed": False,
            },
        }

    def _unavailable_peripheral_payload(
        self,
        peripheral: str,
        command: str,
        exc: HardwareProxyError,
    ) -> dict[str, Any]:
        message, detail = oqlos_error_detail(exc)
        return {
            "ok": False,
            "peripheral_id": peripheral,
            "command": command,
            "error": message,
            "result": {
                "success": False,
                "error": message,
                "detail": detail,
            },
        }

    def _unavailable_command_payload(
        self,
        peripheral: str,
        command: str,
        method: str,
        path: str,
        params: dict[str, Any] | None,
        exc: HardwareProxyError,
    ) -> dict[str, Any]:
        message, detail = oqlos_error_detail(exc)
        return {
            "ok": False,
            "peripheral_id": peripheral,
            "command": command,
            "target": {
                "method": method,
                "path": path,
                "params": params or {},
            },
            "error": message,
            "result": {
                "success": False,
                "error": message,
                "detail": detail,
            },
        }


def normalize_modbus_valve_id(raw: Any) -> str:
    valve_id = str(raw or "valve-1").strip().lower().replace("_", "-")
    if valve_id not in MODBUS_ALLOWED_VALVE_IDS:
        raise HardwareProxyError(
            400,
            (
                f"Unsupported valve_id '{valve_id}' for peripheral 'modbus-io'. "
                "Expected valve-1..valve-14, valve-nc, valve-sc, or valve-wc"
            ),
        )
    return valve_id


def resolve_modbus_target(command: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    valve_id = normalize_modbus_valve_id(args.get("valve_id"))
    if command == "valve_on":
        return "POST", f"/api/v1/hardware/valve/{valve_id}", {"value": True}
    if command == "valve_off":
        return "POST", f"/api/v1/hardware/valve/{valve_id}", {"value": False}
    raise HardwareProxyError(400, f"Unsupported diagnostic command '{command}' for peripheral 'modbus-io'")


def resolve_pump_target(command: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    if command == "pump_set":
        return "POST", "/api/v1/hardware/pump", {"power_pct": float(args.get("power_pct", 20))}
    if command == "pump_off":
        return "POST", "/api/v1/hardware/pump", {"power_pct": 0.0}
    raise HardwareProxyError(400, f"Unsupported diagnostic command '{command}' for peripheral 'motor-dri0050'")


def resolve_lung_target(command: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    if command == "lung_start":
        return "POST", "/api/v1/hardware/lung", {
            "steps": int(args.get("steps", 500)),
            "speed": int(args.get("speed", TIC249_DEFAULT_TARGET_VELOCITY)),
            "cycles": int(args.get("cycles", 3)),
            "pause": float(args.get("pause", 0.5)),
        }
    if command == "lung_stop":
        return "POST", "/api/v1/hardware/lung/stop", None
    if command == "motor_disable":
        return "POST", "/api/v1/hardware/lung/disable", None
    raise HardwareProxyError(400, f"Unsupported diagnostic command '{command}' for peripheral 'motor-tic249'")


def resolve_modbus_adc_target(command: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
    if command == "read_sensor":
        sensor_id = str(args.get("sensor_id") or "ai01")
        return "GET", f"/api/v1/hardware/sensor/{sensor_id}", None
    raise HardwareProxyError(400, f"Unsupported diagnostic command '{command}' for peripheral 'modbus-adc'")


def resolve_diagnostic_target(
    peripheral: str,
    command: str,
    args: dict[str, Any],
) -> tuple[str, str, dict[str, Any] | None]:
    resolvers = {
        "modbus-io": resolve_modbus_target,
        "motor-dri0050": resolve_pump_target,
        "motor-tic249": resolve_lung_target,
        "modbus-adc": resolve_modbus_adc_target,
        "piadc": resolve_modbus_adc_target,
    }
    resolver = resolvers.get(peripheral)
    if not resolver:
        raise HardwareProxyError(
            400,
            f"Unsupported diagnostic command '{command}' for peripheral '{peripheral}'",
        )
    return resolver(command, args)


def extract_command_failure(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None

    if result.get("success") is False:
        return str(result.get("error") or "Command failed")

    nested_ok = result.get("ok")
    if nested_ok is False:
        return str(result.get("error") or "Command failed (ok=false)")
    if isinstance(nested_ok, dict) and nested_ok.get("success") is False:
        return str(nested_ok.get("error") or "Command failed")

    return None
