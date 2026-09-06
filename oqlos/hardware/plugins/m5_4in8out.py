"""M5Stack Module 4In8Out plugin — I2C or StackNet LAN/Wi-Fi output stage.

Command surface is deliberately identical to :mod:`oqlos.hardware.plugins.modbus`
(``set_coil`` / ``set_valve`` / ``all_outputs_off`` / ``read_io_snapshot``) so the
gateway can drive valves through either module without branching. A direct I2C
module exposes 8 outputs; the Core2/CoreS3 HTTP gateway exposes two modules as 16
outputs and 8 inputs.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
from typing import Any
import uuid

from ._m5_core_http import CoreS3HttpClient
from ._maskauth_capability import MaskAuthCapabilityClient
from ._shared import plugin_operation_failure
from .base import HardwarePlugin, PluginConfig, PluginHealth, PluginStatus

logger = logging.getLogger(__name__)

OUTPUT_COUNT = 8
INPUT_COUNT = 4
CORES3_OUTPUT_COUNT = 16
CORES3_INPUT_COUNT = 8
DEFAULT_ADDRESS = 0x45
LEASE_REACQUIRE_ATTEMPTS = 3
_BACKENDS = ("smbus", "mcp2221", "mock")


def _command_failure(message: str, *, status_code: int = 503) -> dict[str, Any]:
    """Keep legacy error text while attaching canonical plugin failure metadata."""
    result = plugin_operation_failure("io-m5-4in8out", message, status_code=status_code)
    result["error"] = message
    return result


class M54In8OutPlugin(HardwarePlugin):
    """
    Plugin for the M5Stack Module 4In8Out valve controller.

    Configuration:
        connection_type: "i2c"
        connection_params:
            backend: "smbus" (native /dev/i2c-N) | "mcp2221" (USB) | "mock"
            bus: 1                  # smbus: /dev/i2c-1
            address: 0x45           # module I2C address
            device_index: 0         # mcp2221: adapter index
            usb_serial: null        # mcp2221: adapter serial
            i2c_freq: 100000        # mcp2221: bus frequency
    """

    PLUGIN_ID = "io-m5-4in8out"
    PLUGIN_NAME = "M5Stack Module 4In8Out"
    PLUGIN_VERSION = "1.0.0"
    PLUGIN_DESCRIPTION = "M5Stack LAN/Wi-Fi gateway for 16x MOSFET output + 8x contact input"
    REQUIRED_PYTHON_PACKAGES = ["m5-4in8out"]
    SUPPORTED_PROTOCOLS = ["i2c", "http"]
    # Alias kept from the Waveshare plugin so callers can use one "all off" address.
    ALL_OUTPUTS_COIL_ADDRESS = 0x00FF

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self._module: Any = None
        self._lock = asyncio.Lock()
        self._lease_task: asyncio.Task[None] | None = None
        self._lease_id = f"boardnet:{socket.gethostname()}:{uuid.uuid4().hex}"

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _params(self) -> dict[str, Any]:
        return self.config.connection_params or {}

    def _address(self) -> int:
        raw = self._params().get("address", DEFAULT_ADDRESS)
        return int(raw, 0) if isinstance(raw, str) else int(raw)

    def _is_http(self) -> bool:
        return self.config.connection_type == "http"

    def _http_token(self) -> str:
        params = self._params()
        explicit = str(params.get("token", "")).strip()
        if explicit:
            return explicit
        token_env = str(params.get("token_env", "STACKNET_OQL_TOKEN")).strip()
        return os.environ.get(token_env, "").strip()

    def _capability_client(self) -> MaskAuthCapabilityClient | None:
        params = self._params()
        base_url = str(params.get("maskauth_url", "")).strip()
        if not base_url:
            return None
        secret_env = str(
            params.get("maskauth_credential_env", "MASKAUTH_BOARDNET_CLIENT_SECRET")
        ).strip()
        secret = os.environ.get(secret_env, "").strip()
        if not secret:
            return None
        return MaskAuthCapabilityClient(
            base_url,
            str(params.get("maskauth_client_id", "boardnet")),
            secret,
            str(params.get("maskauth_application", "boardnet")),
            str(params.get("maskauth_audience", "stacknet")),
            self.config.timeout,
        )

    def _control_credentials_available(self) -> bool:
        return bool(self._http_token() or self._capability_client() is not None)

    def _lease_ttl_ms(self) -> int:
        return int(self._params().get("lease_ttl_ms", 3000))

    def _runtime_configuration(self) -> dict[str, Any] | None:
        value = self._params().get("runtime_configuration")
        return dict(value) if isinstance(value, dict) else None

    @staticmethod
    def _configuration_matches(
        payload: dict[str, Any], desired: dict[str, Any] | None = None
    ) -> bool:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        firmware = data.get("firmware") if isinstance(data.get("firmware"), dict) else {}
        compatibility = (
            firmware.get("oql_compatibility")
            if isinstance(firmware.get("oql_compatibility"), dict)
            else {}
        )
        if not compatibility.get("configured") or not compatibility.get("compatible"):
            return False
        if desired is None:
            return True
        return (
            compatibility.get("active_schema") == desired.get("config_schema")
            and compatibility.get("active_revision") == desired.get("config_revision")
        )

    def validate_config(self) -> list[str]:
        """Validate I2C-specific configuration."""
        errors: list[str] = []
        params = self._params()
        if self.config.connection_type not in {"i2c", "http"}:
            errors.append("m5-4in8out plugin supports i2c or http connection types")
        if self._is_http():
            base_url = str(params.get("base_url", "")).strip()
            if not base_url.startswith(("http://", "https://")):
                errors.append("base_url must start with http:// or https:// for the http transport")
            try:
                lease_ttl_ms = self._lease_ttl_ms()
            except (TypeError, ValueError):
                errors.append("lease_ttl_ms must be an integer")
            else:
                if lease_ttl_ms < 500 or lease_ttl_ms > 10000:
                    errors.append("lease_ttl_ms must be between 500 and 10000")
            return errors

        backend = str(params.get("backend", "smbus")).strip().lower()
        if backend not in _BACKENDS:
            errors.append(f"backend must be one of {', '.join(_BACKENDS)}")

        try:
            address = self._address()
        except (TypeError, ValueError):
            errors.append("address must be an integer (e.g. 0x45)")
        else:
            if not 0x03 <= address <= 0x77:
                errors.append("address must be a valid 7-bit I2C address (0x03-0x77)")

        bus = params.get("bus", 1)
        if backend == "smbus" and (not isinstance(bus, int) or bus < 0):
            errors.append("bus must be a non-negative integer for the smbus backend")

        device_index = params.get("device_index", 0)
        if backend == "mcp2221" and (not isinstance(device_index, int) or device_index < 0):
            errors.append("device_index must be a non-negative integer for the mcp2221 backend")

        return errors

    def _build_module(self) -> Any:
        from m5_4in8out import Module4In8Out, Module4In8OutConfig

        params = self._params()
        config = Module4In8OutConfig(
            address=self._address(),
            backend=str(params.get("backend", "smbus")).strip().lower(),
            bus=int(params.get("bus", 1)),
            device_index=int(params.get("device_index", 0)),
            usb_serial=params.get("usb_serial"),
            i2c_freq=int(params.get("i2c_freq", 100_000)),
        )
        return Module4In8Out(config)

    def _http_health_from_payload(
        self,
        payload: dict[str, Any],
        *,
        require_control_lease: bool,
    ) -> PluginHealth:
        """Separate physical M122 health from permission to actuate outputs."""
        data = payload.get("data") or {}
        modules = data.get("modules") or []
        physical_healthy = self._m122_modules_healthy(data, modules)
        configuration_compatible = self._configuration_matches(payload)
        control_credentials_available = self._control_credentials_available()
        lease_active = bool(
            getattr(self._module, "lease_id", "")
            and self._lease_task is not None
            and not self._lease_task.done()
        )
        control_ready = physical_healthy and (
            lease_active or not require_control_lease
        ) and (configuration_compatible or not require_control_lease)
        if not physical_healthy:
            message = "StackNet reachable; one or more M122 modules unavailable"
        elif require_control_lease and not control_credentials_available:
            message = "StackNet dual M122 online; control authorization unavailable"
        elif require_control_lease and not lease_active:
            message = "StackNet dual M122 online; control lease unavailable"
        elif require_control_lease and not configuration_compatible:
            message = "StackNet dual M122 online; OQL configuration unavailable or incompatible"
        else:
            message = "StackNet dual M122 online"
        return PluginHealth(
            # A physically healthy read-only StackNet is configured and
            # reachable.  Keep ``compatible`` false until control is armed so
            # HUI actions remain fail-closed, while the health endpoint can
            # distinguish missing authorization/lease from a dead M122 bus.
            status=(
                PluginStatus.CONNECTED
                if control_ready
                else PluginStatus.CONFIGURED
                if physical_healthy
                else PluginStatus.ERROR
            ),
            message=message,
            details={
                "backend": "cores3-http",
                "base_url": self._params().get("base_url"),
                "transport_reachable": True,
                "modules": modules,
                "address": ", ".join(str(item.get("address")) for item in modules),
                "physical_healthy": physical_healthy,
                "control_ready": control_ready,
                "control_credentials_available": control_credentials_available,
                "control_lease_active": lease_active,
                "oql_configuration_compatible": configuration_compatible,
            },
            compatible=control_ready,
            version=",".join(
                str(item.get("firmware_version", "?")) for item in modules
            ),
        )

    @staticmethod
    def _m122_modules_healthy(
        data: dict[str, Any], modules: list[dict[str, Any]]
    ) -> bool:
        """Derive valve-module health without inheriting unrelated node faults.

        StackNet's top-level ``healthy`` describes its complete hardware
        profile.  It can therefore be false when DRI0050 or another sibling
        component is absent even though both M122 modules answer correctly.
        New firmware publishes an explicit module inventory; older firmware
        falls back to the aggregate flag.
        """
        if not modules:
            return bool(data.get("healthy"))

        i2c = data.get("i2c") if isinstance(data.get("i2c"), dict) else {}
        expected = i2c.get("m122_module_count", 2)
        try:
            expected_count = max(1, int(expected))
        except (TypeError, ValueError):
            expected_count = 2

        present_modules = [
            module
            for module in modules
            if isinstance(module, dict) and module.get("present", True) is not False
        ]
        return len(present_modules) >= expected_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Open the I2C transport and probe the module."""
        if self._is_http():
            params = self._params()
            self._module = CoreS3HttpClient(
                str(params.get("base_url", "")),
                self._http_token(),
                self.config.timeout,
                self._capability_client(),
            )
            attempts = max(1, int(self.config.retry_count) + 1)
            for attempt in range(attempts):
                async with self._lock:
                    payload = await asyncio.wait_for(
                        asyncio.to_thread(self._module.status),
                        timeout=self.config.timeout,
                    )
                health = self._http_health_from_payload(
                    payload,
                    require_control_lease=False,
                )
                if health.details.get("transport_reachable") and not health.details.get(
                    "physical_healthy"
                ):
                    self._status = PluginStatus.CONNECTED
                    logger.warning(
                        "StackNet connected diagnostic-only; one or more M122 modules unavailable"
                    )
                    return True
                if health.status == PluginStatus.CONNECTED and health.compatible:
                    if not self._control_credentials_available():
                        self._status = PluginStatus.CONNECTED
                        logger.warning(
                            "StackNet connected read-only; control authorization unavailable"
                        )
                        return True
                    try:
                        await self._call("acquire_lease", self._lease_id, self._lease_ttl_ms())
                        desired = self._runtime_configuration()
                        if desired is not None and not self._configuration_matches(payload, desired):
                            await self._call("execute", "config_apply", desired)
                            confirmed = False
                            for confirmation_attempt in range(attempts + 2):
                                if confirmation_attempt:
                                    await asyncio.sleep(min(0.25 * confirmation_attempt, 1.0))
                                try:
                                    payload = await self._call("status")
                                except Exception:
                                    continue
                                if self._configuration_matches(payload, desired):
                                    confirmed = True
                                    break
                            if not confirmed:
                                raise RuntimeError(
                                    "StackNet did not confirm the configured OQL schema/revision"
                                )
                            # Configuration may rebind the network interface.
                            # Refresh the lease after confirmation so the first
                            # renewal never relies on the pre-apply deadline.
                            await self._call("acquire_lease", self._lease_id, self._lease_ttl_ms())
                    except Exception as exc:
                        logger.error("StackNet control preparation failed: %s", exc)
                        self._module.close()
                        self._module = None
                        self._status = PluginStatus.ERROR
                        return False
                    self._lease_task = asyncio.create_task(self._renew_http_lease())
                    final_health = self._http_health_from_payload(
                        payload,
                        require_control_lease=True,
                    )
                    if not final_health.compatible:
                        await self.disconnect()
                        self._status = PluginStatus.ERROR
                        return False
                    self._status = PluginStatus.CONNECTED
                    return True
                if attempt + 1 < attempts:
                    await asyncio.sleep(min(0.25 * (attempt + 1), 1.0))
            self._module = None
            self._status = PluginStatus.ERROR
            return False
        try:
            from m5_4in8out import Module4In8Out  # noqa: F401
        except ImportError:
            logger.error("m5-4in8out is not installed for the io-m5-4in8out plugin")
            self._status = PluginStatus.INCOMPATIBLE
            return False

        try:
            module = await asyncio.to_thread(self._build_module)
        except Exception as exc:
            self._status = PluginStatus.ERROR
            logger.error("Failed to open 4In8Out I2C transport: %s", exc)
            return False

        self._module = module
        health = await self.health_check()
        if health.compatible:
            self._status = PluginStatus.CONNECTED
            logger.info(
                "Connected to 4In8Out at 0x%02X via %s",
                self._address(),
                self._params().get("backend", "smbus"),
            )
            return True

        logger.error(
            "4In8Out transport opened but the module did not answer at 0x%02X: %s",
            self._address(),
            health.message,
        )
        await self.disconnect()
        self._status = PluginStatus.ERROR
        return False

    async def disconnect(self) -> None:
        """Close the I2C transport."""
        if self._lease_task is not None:
            self._lease_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._lease_task
            self._lease_task = None
        module, self._module = self._module, None
        if module is not None:
            try:
                if self._is_http():
                    await asyncio.to_thread(module.release_lease)
                await asyncio.to_thread(module.close)
            except Exception:
                logger.debug("Failed to close 4In8Out transport", exc_info=True)
        self._status = PluginStatus.CONFIGURED
        logger.info("Disconnected from 4In8Out")

    async def health_check(self) -> PluginHealth:
        """Probe the module without changing output state."""
        if self._module is None and self._is_http():
            params = self._params()
            self._module = CoreS3HttpClient(
                str(params.get("base_url", "")),
                self._http_token(),
                self.config.timeout,
                self._capability_client(),
            )
        if self._module is None:
            address = self._address()
            bus = int(self._params().get("bus", 1))
            logger.warning(
                "io-m5-4in8out issue_code=hw_m5_4in8out_no_response "
                "not_connected address=0x%02X bus=%s",
                address,
                bus,
            )
            return PluginHealth(
                status=PluginStatus.ERROR,
                message=(
                    f"Not connected to 4In8Out at 0x{address:02X} on /dev/i2c-{bus}; "
                    f"expected on i2cdetect -y {bus}"
                ),
                details={
                    "operator_alerts": [
                        {
                            "issue_code": "hw_m5_4in8out_no_response",
                            "message": (
                                f"Moduł M5 4In8Out nie odpowiada na I2C 0x{address:02X} "
                                f"(/dev/i2c-{bus}; i2cdetect -y {bus})."
                            ),
                        }
                    ]
                },
                compatible=False,
            )
        try:
            async with self._lock:
                if self._is_http():
                    payload = await asyncio.wait_for(
                        asyncio.to_thread(self._module.status), timeout=self.config.timeout
                    )
                    return self._http_health_from_payload(
                        payload,
                        require_control_lease=True,
                    )
                status = await asyncio.wait_for(
                    asyncio.to_thread(self._module.health),
                    timeout=self.config.timeout,
                )
        except asyncio.TimeoutError:
            return PluginHealth(
                status=PluginStatus.ERROR,
                message=f"4In8Out probe timed out after {self.config.timeout:.1f}s",
                compatible=False,
            )
        except Exception as exc:
            if self._is_http():
                self._module = None
                base_url = str(self._params().get("base_url", "")).rstrip("/")
                return PluginHealth(
                    status=PluginStatus.ERROR,
                    message=f"StackNet LAN/Wi-Fi gateway unavailable at {base_url}: {exc}",
                    details={
                        "backend": "cores3-http",
                        "base_url": base_url,
                        "transport_reachable": False,
                        "operator_alerts": [
                            {
                                "issue_code": "hw_m5_4in8out_no_response",
                                "message": (
                                    "Brak odpowiedzi StackNet przez LAN/Wi-Fi; sprawdź sieć, "
                                    "zasilanie i endpoint /api/v1/oql/status."
                                ),
                            }
                        ],
                    },
                    compatible=False,
                )
            return PluginHealth(
                status=PluginStatus.ERROR,
                message=f"Health check exception: {exc}",
                compatible=False,
            )

        if status.healthy:
            return PluginHealth(
                status=PluginStatus.CONNECTED,
                message=status.message,
                details=dict(status.details),
                compatible=True,
                version=str(status.details.get("firmware_version", "unknown")),
            )
        return PluginHealth(
            status=PluginStatus.ERROR,
            message=status.message,
            details=dict(status.details),
            compatible=False,
        )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def _call(self, method: str, *args: Any) -> Any:
        async with self._lock:
            return await asyncio.wait_for(
                asyncio.to_thread(getattr(self._module, method), *args),
                timeout=self.config.timeout,
            )

    async def _reacquire_http_lease(self) -> bool:
        """Re-arm a lost lease. The dead-man already forced every output off."""
        for attempt in range(LEASE_REACQUIRE_ATTEMPTS):
            if attempt:
                await asyncio.sleep(min(0.25 * attempt, 1.0))
            try:
                await self._call("acquire_lease", self._lease_id, self._lease_ttl_ms())
            except asyncio.CancelledError:
                raise
            except Exception:
                continue
            return True
        return False

    async def _renew_http_lease(self) -> None:
        interval = max(0.2, self._lease_ttl_ms() / 3000.0)
        while True:
            await asyncio.sleep(interval)
            try:
                await self._call("renew_lease")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # A single refused renewal (StackNet reboot, dropped network frame,
                # HTTP 409 on an expired lease) must not brick the valve stage
                # until the whole service restarts: re-arming cannot energize an
                # output, because the dead-man already forced all-off.
                logger.warning(
                    "StackNet control lease renewal failed; re-acquiring: %s", exc
                )
                if await self._reacquire_http_lease():
                    continue
                self._status = PluginStatus.ERROR
                logger.error("StackNet control lease renewal failed; dead-man will force all-off: %s", exc)
                return

    async def _execute_set_coil(self, params: dict[str, Any]) -> dict[str, Any]:
        """Write one output; the Waveshare 'all outputs' address is honoured too."""
        if "coil" not in params:
            return _command_failure("coil is required", status_code=422)
        coil = params.get("coil")
        value = bool(params.get("value", False))
        if not isinstance(coil, int) or isinstance(coil, bool) or coil < 0:
            return _command_failure("coil must be a non-negative integer", status_code=422)
        if coil == self.ALL_OUTPUTS_COIL_ADDRESS:
            if not value:
                return await self._execute_all_outputs_off()
            outputs = await self._call("set_all_outputs", True)
            return {
                "success": True,
                "data": {"all_outputs": True, "outputs": list(outputs)},
            }
        output_count = CORES3_OUTPUT_COUNT if self._is_http() else OUTPUT_COUNT
        if coil >= output_count:
            return _command_failure(f"coil must be 0..{output_count - 1} on the configured 4In8Out transport", status_code=422)
        # Coils keep the zero-based Modbus wire contract (coil 0 = first output);
        # the module and both vendor drivers number outputs OUT1..OUT8.
        await self._call("set_output", coil + 1, value)
        return {
            "success": True,
            "data": {"coil": coil, "value": value, "output": coil + 1},
        }

    async def _execute_set_valve(self, params: dict[str, Any]) -> dict[str, Any]:
        """Map valve_id to an output channel using the canonical catalogue."""
        from oqlos.api.command_kwargs import pick_param
        from oqlos.hardware.modbus_io_catalog import resolve_valve_coil

        valve_id = pick_param(params, "valve_id", "valveId")
        if not valve_id:
            return _command_failure("valve_id is required", status_code=422)
        coil = resolve_valve_coil(str(valve_id))
        if coil is None:
            return _command_failure(f"Unknown valve_id: {valve_id}", status_code=422)
        return await self.execute_command(
            "set_coil",
            {"coil": coil, "value": pick_param(params, "value", default=False)},
        )

    async def _execute_all_outputs_off(self) -> dict[str, Any]:
        """Safe state: de-energize every output in one sequential write."""
        outputs = await self._call("all_outputs_off")
        return {
            "success": True,
            "data": {"all_outputs": True, "outputs": list(outputs)},
        }

    async def _execute_read_io_snapshot(self) -> dict[str, Any]:
        snapshot = await self._call("read_snapshot")
        data = snapshot.as_dict()
        return {
            "success": True,
            "data": {
                # `coils` / `discrete_inputs` keep the modbus-io wire shape so
                # hardware-coils UI and diagnostics stay backend-agnostic.
                "coils": list(data["outputs"]),
                "discrete_inputs": list(data["inputs"]),
                "outputs": list(data["outputs"]),
                "inputs": list(data["inputs"]),
                "firmware_version": data["firmware_version"],
                "address": f"0x{self._address():02X}",
            },
        }

    async def _execute_http_read_io_snapshot(self) -> dict[str, Any]:
        """Read StackNet state without requiring an actuation lease.

        StackNet publishes the current input/output snapshot on its public
        status endpoint.  Keeping this path separate from ``execute`` lets a
        physically healthy node remain observable while MaskAuth, the control
        lease, or the active OQL configuration is unavailable.
        """
        if self._module is None:
            client = CoreS3HttpClient(
                str(self._params().get("base_url", "")),
                self._http_token(),
                self.config.timeout,
                self._capability_client(),
            )
            try:
                payload = await asyncio.wait_for(
                    asyncio.to_thread(client.status),
                    timeout=self.config.timeout,
                )
            finally:
                client.close()
        else:
            payload = await self._call("status")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        outputs = data.get("outputs") if isinstance(data.get("outputs"), list) else []
        inputs = data.get("inputs") if isinstance(data.get("inputs"), list) else []
        modules = data.get("modules") if isinstance(data.get("modules"), list) else []
        firmware = data.get("firmware") if isinstance(data.get("firmware"), dict) else {}
        health = self._http_health_from_payload(payload, require_control_lease=True)
        snapshot_data = dict(data)
        snapshot_data.update(
            {
                # `coils` / `discrete_inputs` retain the Modbus-compatible wire
                # shape while the remaining public StackNet inventory stays
                # available to read-only gateways such as the C2004 process
                # runtime.
                "coils": [bool(value) for value in outputs],
                "discrete_inputs": [bool(value) for value in inputs],
                "outputs": [bool(value) for value in outputs],
                "inputs": [bool(value) for value in inputs],
                "firmware_version": firmware.get("version") or "",
                "address": ", ".join(
                    str(module.get("address"))
                    for module in modules
                    if isinstance(module, dict) and module.get("address")
                ),
                "backend": "cores3-http",
                "physical_healthy": bool(health.details.get("physical_healthy")),
                "control_ready": bool(health.compatible),
                "control_message": health.message,
            }
        )
        return {
            "success": True,
            "data": snapshot_data,
        }

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a 4In8Out command."""
        if self._is_http() and command == "read_io_snapshot":
            try:
                return await self._execute_http_read_io_snapshot()
            except asyncio.TimeoutError:
                return _command_failure(f"4In8Out command timed out after {self.config.timeout:.1f}s")
            except Exception as exc:
                return _command_failure(str(exc))
        if self._module is None:
            return _command_failure("Not connected to 4In8Out")
        if self._is_http() and not self._control_credentials_available():
            return _command_failure("StackNet control authorization unavailable; read-only connection")
        if self._is_http() and (
            self._lease_task is None or self._lease_task.done()
        ):
            return _command_failure("StackNet control lease unavailable; read-only connection")
        try:
            if self._is_http():
                if command == "set_valve":
                    from oqlos.api.command_kwargs import pick_param
                    from oqlos.hardware.modbus_io_catalog import resolve_valve_coil
                    valve_id = pick_param(params, "valve_id", "valveId")
                    coil = resolve_valve_coil(str(valve_id)) if valve_id else None
                    if coil is None:
                        return _command_failure(f"Unknown valve_id: {valve_id}", status_code=422)
                    command = "set_coil"
                    params = {"coil": coil, "value": pick_param(params, "value", default=False)}
                elif command == "replace_valves":
                    from oqlos.hardware.modbus_io_catalog import resolve_valve_coil
                    valve_ids = params.get("valve_ids")
                    if not isinstance(valve_ids, (list, tuple)):
                        return _command_failure("valve_ids must be a list", status_code=422)
                    mask = 0
                    for valve_id in valve_ids:
                        coil = resolve_valve_coil(str(valve_id))
                        if coil is None or coil >= CORES3_OUTPUT_COUNT:
                            return _command_failure(f"Unknown valve_id: {valve_id}", status_code=422)
                        mask |= 1 << coil
                    command = "replace_outputs"
                    params = {"mask": mask}
                return await self._call("execute", command, params)
            if command == "set_coil":
                return await self._execute_set_coil(params)
            if command == "set_valve":
                return await self._execute_set_valve(params)
            if command == "all_outputs_off":
                return await self._execute_all_outputs_off()
            if command == "read_io_snapshot":
                return await self._execute_read_io_snapshot()
            return _command_failure(f"Unknown command: {command}", status_code=422)
        except asyncio.TimeoutError:
            return _command_failure(f"4In8Out command timed out after {self.config.timeout:.1f}s")
        except Exception as exc:
            return _command_failure(str(exc))

    @classmethod
    def get_capabilities(cls) -> dict[str, Any]:
        """Return 4In8Out plugin capabilities."""
        from oqlos.hardware.modbus_io_catalog import VALVE_COIL_MAP

        capabilities = super().get_capabilities()
        capabilities.update({
            "supported_commands": [
                "set_coil",
                "set_valve",
                "replace_valves",
                "all_outputs_off",
                "read_io_snapshot",
            ],
            "valve_mapping": dict(VALVE_COIL_MAP),
            "outputs": CORES3_OUTPUT_COUNT,
            "inputs": CORES3_INPUT_COUNT,
            "configuration_schema": {
                "connection_type": {"type": "string", "enum": ["i2c", "http"], "default": "http"},
                "connection_params": {
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "enum": list(_BACKENDS),
                            "default": "smbus",
                        },
                        "bus": {"type": "integer", "default": 1, "minimum": 0},
                        "address": {"type": "integer", "default": DEFAULT_ADDRESS},
                        "device_index": {"type": "integer", "default": 0, "minimum": 0},
                        "usb_serial": {"type": "string"},
                        "i2c_freq": {"type": "integer", "default": 100000},
                        "base_url": {"type": "string", "default": "http://stacknet.local:8080"},
                        "token": {"type": "string"},
                    },
                },
            },
        })
        return capabilities
