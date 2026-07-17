"""Async httpx proxy to OqlOS hardware REST API."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from oqlos.hardware.client.adc import normalize_adc_read_all_result, normalize_adc_read_result
from oqlos.hardware.client.config import (
    OqlosHardwareProxyConfig,
    candidate_oqlos_bases,
    float_from_env,
    int_from_env,
)
from oqlos.hardware.client.constants import (
    ARTIFICIAL_LUNG_IDS,
    FALLBACK_ADAPTERS,
    PERIPHERAL_STATUS_COMMANDS,
    PERIPHERAL_STATUS_PLUGIN_ALIASES,
)
from oqlos.hardware.client.errors import HardwareProxyError, is_oqlos_unavailable, oqlos_error_detail
from oqlos.hardware.client.http_helpers import response_error_message, safe_response_payload
from oqlos.hardware.client.resolvers import extract_command_failure, resolve_diagnostic_target


def _is_unsuccessful_result(result: Any) -> bool:
    return isinstance(result, dict) and result.get("success") is False


def _classify_unavailable_reason(
    message: str,
    detail: Any,
    status_code: int | None = None,
) -> str:
    """Classify why OqlOS health is unavailable for user-facing preflight.

    Returns one of: ``updating``, ``restarting``, ``unreachable``.
    """
    parts: list[str] = [str(message or "")]
    if isinstance(detail, dict):
        for key in ("error", "message", "last_error", "reason", "status", "detail"):
            if detail.get(key) is not None:
                parts.append(str(detail.get(key)))
        body = detail.get("response")
        if isinstance(body, dict):
            for key in ("error", "message", "reason", "status", "mode"):
                if body.get(key) is not None:
                    parts.append(str(body.get(key)))
            if body.get("updating") is True or body.get("maintenance") is True:
                return "updating"
    elif detail is not None:
        parts.append(str(detail))
    blob = " ".join(parts).lower()

    update_markers = (
        "updat",
        "upgrade",
        "redeploy",
        "deploy in progress",
        "maintenance",
        "migrat",
        "aktualizac",
    )
    if any(marker in blob for marker in update_markers):
        return "updating"

    restart_markers = (
        "connection refused",
        "connect call failed",
        "errno 111",
        "temporarily unavailable",
        "service is not ready",
        "restart",
        "starting",
        "activating",
        "reloading",
    )
    if any(marker in blob for marker in restart_markers):
        return "restarting"

    # 503 without a real health body often means process up but not serving yet.
    if status_code == 503:
        return "restarting"
    return "unreachable"


class OqlosHardwareProxy:
    def __init__(
        self,
        config: OqlosHardwareProxyConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        unavailable_source: str = "oqlos.hardware.client",
    ) -> None:
        self.config = config or OqlosHardwareProxyConfig.from_env()
        self._client: httpx.AsyncClient | None = client
        self._unavailable_source = unavailable_source

    def candidate_bases(self) -> list[str]:
        return candidate_oqlos_bases(self.config.api_base)

    def proxy_info(self) -> dict[str, Any]:
        return {
            "oqlos_api_base": self.config.api_base,
            "oqlos_api_candidates": self.candidate_bases(),
            "oqlos_api_timeout_seconds": self.config.timeout_seconds,
            "oqlos_api_identify_timeout_seconds": self.config.identify_timeout_seconds,
            "proxy_prefix": self.config.proxy_prefix,
            "hardware_runtime_name": self.config.runtime_name,
            "hardware_runtime_url": self.config.api_base,
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

        # Transient-failure retries: sweep the full candidate list `retries+1` times.
        # HTTP status errors (4xx/5xx from a reachable OqlOS) short-circuit — only
        # connection-level errors are retried.
        retries = max(0, int_from_env(os.environ, "OQLOS_TRANSIENT_RETRIES", 1))
        retry_delay = max(0.0, float_from_env(os.environ, "OQLOS_TRANSIENT_RETRY_DELAY", 0.25))
        sweeps = retries + 1
        last_error: httpx.HTTPError | None = None
        attempt = 0
        for attempt in range(1, sweeps + 1):
            for target in targets:
                try:
                    res = await client.request(method, target, params=params, json=payload, timeout=req_timeout)
                    res.raise_for_status()
                    return res.json()
                except httpx.HTTPStatusError as exc:
                    response_payload = safe_response_payload(exc.response)
                    response_detail = response_error_message(response_payload)
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
            if attempt < sweeps and retry_delay > 0:
                await asyncio.sleep(retry_delay)
        raise HardwareProxyError(
            502,
            {
                "error": f"Cannot reach OqlOS API for {normalized_path}",
                "attempts": attempt,
                "attempted_targets": targets,
                "last_error": str(last_error) if last_error else "unknown error",
                "timeout_seconds": timeout if timeout is not None else self.config.timeout_seconds,
            },
        )

    def _degraded_oqlos_payload(self, exc: HardwareProxyError) -> dict[str, Any] | None:
        """OqlOS may return HTTP 503 with a real-mode health body when plugins are degraded."""
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        body = detail.get("response")
        if not isinstance(body, dict):
            return None
        mode = str(body.get("mode") or "").lower()
        if mode not in {"real", "degraded"}:
            return None
        return {
            **body,
            "degraded": True,
            "overall_ok": bool(body.get("ok")),
            "proxy_degraded": True,
        }

    async def health(self) -> dict[str, Any]:
        path = "/api/v1/hardware/health"
        try:
            return await self._proxy_oqlos(path, timeout=self.config.timeout_seconds)
        except HardwareProxyError as exc:
            degraded = self._degraded_oqlos_payload(exc)
            if degraded is not None:
                return degraded
            if is_oqlos_unavailable(exc):
                return self._unavailable_health_payload(exc, path)
            raise

    async def identify(self) -> dict[str, Any]:
        try:
            return await self._proxy_oqlos_request(
                "GET",
                "/api/v1/hardware/identify",
                params={"scan": os.getenv("OQLOS_IDENTIFY_SCAN_MODE", "never")},
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
        response: dict[str, Any] = {"ok": ok, "peripheral_id": peripheral, "command": command, "result": result}
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
                peripheral, command, method, path, params
            )
        except HardwareProxyError as exc:
            if is_oqlos_unavailable(exc):
                return self._unavailable_command_payload(peripheral, command, method, path, params, exc)
            raise
        failure = extract_command_failure(result)
        if failure and peripheral == "motor-dri0050" and command in {"pump_off", "pump_set"}:
            failure = await self._enrich_motor_dri0050_failure(failure)
        return {
            "ok": failure is None,
            "peripheral_id": peripheral,
            "command": command,
            "target": {"method": method, "path": path, "params": params or {}},
            **({"error": failure} if failure else {}),
            "result": result,
        }

    def _motor_api_bases(self) -> list[str]:
        raw = (
            os.getenv("OQLOS_MOTOR_URL")
            or os.getenv("MOTOR_URL")
            or "http://host.docker.internal:8203"
        )
        base = raw.rstrip("/")
        return [base] if base else []

    async def _fetch_dri0050_motor_health_hint(self) -> str:
        """Read DRI0050 sidecar /health (port 8203) when OqlOS plugin health is empty."""
        client = self._get_client()
        timeout = httpx.Timeout(3.0, connect=self.config.connect_timeout_seconds)
        for base in self._motor_api_bases():
            try:
                response = await client.get(f"{base}/health", timeout=timeout)
                payload = response.json()
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            message = str(payload.get("message") or "").strip()
            if message:
                return message
            port = str(payload.get("port") or "").strip()
            if port:
                return f"serial port {port} not responding"
        return ""

    @staticmethod
    def _is_useless_motor_health_hint(hint: str) -> bool:
        normalized = hint.strip().rstrip(":").lower()
        return not normalized or normalized == "health check exception"

    @staticmethod
    def _should_enrich_motor_dri0050_failure(failure: str) -> bool:
        normalized = failure.strip()
        if not normalized:
            return True
        if "no error detail" in normalized.lower() or normalized == "Command failed":
            return True
        if "motor plugin not available" in normalized.lower():
            return True
        if normalized.startswith("HTTP ") and normalized[5:].isdigit():
            return True
        return False

    @staticmethod
    def _motor_dri0050_remediation(failure: str, hint: str) -> str:
        combined = f"{failure} {hint}".lower()
        if "motor plugin not available" in combined or "input/output error" in combined or "write timeout" in combined:
            return (
                " Restart: systemctl --user restart dri0050-motor-api && "
                "systemctl --user restart oqlos-hardware-api.service"
            )
        return ""

    async def _enrich_motor_dri0050_failure(self, failure: str) -> str:
        """Append motor-dri0050 health when OqlOS returns a generic driver error."""
        if not self._should_enrich_motor_dri0050_failure(failure):
            return failure
        hint = ""
        try:
            health = await self._proxy_oqlos_request("GET", "/api/v1/plugins/motor-dri0050/health")
            if isinstance(health, dict):
                hint = str(health.get("message") or "").strip()
        except HardwareProxyError:
            pass
        if self._is_useless_motor_health_hint(hint):
            hint = await self._fetch_dri0050_motor_health_hint()
        remediation = self._motor_dri0050_remediation(failure, hint)
        if hint:
            return f"DRI0050 pump command failed: {hint}.{remediation}"
        if remediation:
            return f"{failure}.{remediation}"
        return failure

    async def _load_peripheral_status(self, peripheral: str) -> tuple[str, Any, bool]:
        command = PERIPHERAL_STATUS_COMMANDS[peripheral]
        plugin_peripheral = PERIPHERAL_STATUS_PLUGIN_ALIASES.get(peripheral, peripheral)
        if peripheral == "modbus-io":
            return command, *await self._load_modbus_io_status(peripheral)
        if peripheral in {"modbus-adc", "piadc"}:
            return command, *await self._load_adc_status()
        if peripheral == "rtc":
            return command, *await self._load_simple_hardware_status("/api/v1/hardware/rtc/status")
        if peripheral in ARTIFICIAL_LUNG_IDS:
            return command, *await self._load_simple_hardware_status("/api/v1/hardware/artificial-lung/status")
        return command, *await self._load_plugin_status(plugin_peripheral, command)

    async def _load_modbus_io_status(self, peripheral: str) -> tuple[Any, bool]:
        result = await self._proxy_oqlos_request("GET", f"/api/v1/plugins/{peripheral}/health")
        if not isinstance(result, dict):
            return result, False
        status = str(result.get("status") or "").lower()
        ok = result.get("success") is not False and (
            bool(result.get("compatible")) or status in {"healthy", "connected", "ok"}
        )
        return result, ok

    async def _load_adc_status(self) -> tuple[Any, bool]:
        result = await self._proxy_oqlos_request("GET", "/api/v1/hardware/sensor/ai01")
        result = normalize_adc_read_result(result, "v1")
        return result, not _is_unsuccessful_result(result)

    async def _load_simple_hardware_status(self, path: str) -> tuple[Any, bool]:
        result = await self._proxy_oqlos_request("GET", path)
        return result, not (isinstance(result, dict) and result.get("ok") is False)

    async def _load_plugin_status(self, plugin_peripheral: str, command: str) -> tuple[Any, bool]:
        result = await self._proxy_oqlos_request(
            "POST",
            f"/api/v1/plugins/{plugin_peripheral}/execute",
            payload={"command": command, "params": {}},
        )
        ok = not _is_unsuccessful_result(result)
        if plugin_peripheral == "motor-tic249" and isinstance(result, dict):
            data = result.get("data") if isinstance(result.get("data"), dict) else result
            if isinstance(data, dict) and data.get("connected") is False:
                ok = False
        return result, ok

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
        if peripheral in ARTIFICIAL_LUNG_IDS:
            result = await self._proxy_oqlos_request(method, path, payload=params)
            return method, path, params, result
        if peripheral == "rtc":
            result = await self._proxy_oqlos_request(method, path, payload=params)
            return method, path, params, result
        if peripheral in {"modbus-adc", "piadc"}:
            if command == "read_all":
                result = await self._proxy_oqlos_request(
                    method,
                    path,
                    payload={"command": "read_all", "params": {}},
                )
                return method, path, params, normalize_adc_read_all_result(result)
            if command == "read_sensor":
                result = await self._proxy_oqlos_request(method, path, params=params)
                requested_sensor_id = path.rsplit("/", 1)[-1]
                return method, path, params, normalize_adc_read_result(result, requested_sensor_id)
        result = await self._proxy_oqlos_request(method, path, params=params)
        return method, path, params, result

    def _unavailable_health_payload(self, exc: HardwareProxyError, path: str) -> dict[str, Any]:
        message, detail = oqlos_error_detail(exc)
        reason = _classify_unavailable_reason(message, detail, exc.status_code)
        payload: dict[str, Any] = {
            "status": "unavailable",
            "ok": False,
            "mode": "unavailable",
            "reason": reason,
            "error": message,
            "detail": detail,
            "proxy": {
                "path": path,
                "oqlos_api_base": self.config.api_base,
                "oqlos_api_candidates": self.candidate_bases(),
            },
        }
        if reason == "updating":
            payload["updating"] = True
            payload["maintenance"] = True
        return payload

    def _unavailable_identify_payload(self, exc: HardwareProxyError) -> dict[str, Any]:
        health = self._unavailable_health_payload(exc, "/api/v1/hardware/identify")
        adapters = [
            {
                **adapter,
                "status": "no-access",
                "probe": {
                    "connected": False,
                    "source": self._unavailable_source,
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
            "diagnostics": {"health": health, "scan_mode": "proxy", "scan_performed": False},
        }

    def _unavailable_peripheral_payload(self, peripheral: str, command: str, exc: HardwareProxyError) -> dict[str, Any]:
        message, detail = oqlos_error_detail(exc)
        return {
            "ok": False,
            "peripheral_id": peripheral,
            "command": command,
            "error": message,
            "result": {"success": False, "error": message, "detail": detail},
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
            "target": {"method": method, "path": path, "params": params or {}},
            "error": message,
            "result": {"success": False, "error": message, "detail": detail},
        }
