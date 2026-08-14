"""M5Stack Module 4In8Out plugin — I2C valve output stage.

Command surface is deliberately identical to :mod:`oqlos.hardware.plugins.modbus`
(``set_coil`` / ``set_valve`` / ``all_outputs_off`` / ``read_io_snapshot``) so the
gateway can drive valves through either module without branching. Channel
identity follows the same canonical catalogue: ``valve-1..8`` → output 0..7.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import HardwarePlugin, PluginConfig, PluginHealth, PluginStatus

logger = logging.getLogger(__name__)

OUTPUT_COUNT = 8
INPUT_COUNT = 4
DEFAULT_ADDRESS = 0x45
_BACKENDS = ("smbus", "mcp2221", "mock")


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
    PLUGIN_DESCRIPTION = "8x MOSFET output + 4x contact input I2C module — valve & signal control"
    REQUIRED_PYTHON_PACKAGES = ["m5-4in8out"]
    SUPPORTED_PROTOCOLS = ["i2c"]
    # Alias kept from the Waveshare plugin so callers can use one "all off" address.
    ALL_OUTPUTS_COIL_ADDRESS = 0x00FF

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self._module: Any = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _params(self) -> dict[str, Any]:
        return self.config.connection_params or {}

    def _address(self) -> int:
        raw = self._params().get("address", DEFAULT_ADDRESS)
        return int(raw, 0) if isinstance(raw, str) else int(raw)

    def validate_config(self) -> list[str]:
        """Validate I2C-specific configuration."""
        errors: list[str] = []
        if self.config.connection_type != "i2c":
            errors.append("m5-4in8out plugin supports the i2c connection type")

        params = self._params()
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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Open the I2C transport and probe the module."""
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
        module, self._module = self._module, None
        if module is not None:
            try:
                await asyncio.to_thread(module.close)
            except Exception:
                logger.debug("Failed to close 4In8Out transport", exc_info=True)
        self._status = PluginStatus.CONFIGURED
        logger.info("Disconnected from 4In8Out")

    async def health_check(self) -> PluginHealth:
        """Probe the module without changing output state."""
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

    async def _execute_set_coil(self, params: dict[str, Any]) -> dict[str, Any]:
        """Write one output; the Waveshare 'all outputs' address is honoured too."""
        coil = params.get("coil", 0)
        value = bool(params.get("value", False))
        if not isinstance(coil, int) or isinstance(coil, bool) or coil < 0:
            return {"success": False, "error": "coil must be a non-negative integer"}
        if coil == self.ALL_OUTPUTS_COIL_ADDRESS:
            if not value:
                return await self._execute_all_outputs_off()
            outputs = await self._call("set_all_outputs", True)
            return {
                "success": True,
                "data": {"all_outputs": True, "outputs": list(outputs)},
            }
        if coil >= OUTPUT_COUNT:
            return {
                "success": False,
                "error": f"coil must be 0..{OUTPUT_COUNT - 1} on the 4In8Out module",
            }
        # Coils keep the zero-based Modbus wire contract (coil 0 = first output);
        # the module and both vendor drivers number outputs OUT1..OUT8.
        await self._call("set_output", coil + 1, value)
        return {
            "success": True,
            "data": {"coil": coil, "value": value, "output": coil + 1},
        }

    async def _execute_set_valve(self, params: dict[str, Any]) -> dict[str, Any]:
        """Map valve_id to an output channel using the canonical catalogue."""
        from oqlos.hardware.modbus_io_catalog import resolve_valve_coil

        valve_id = params.get("valve_id")
        if not valve_id:
            return {"success": False, "error": "valve_id is required"}
        coil = resolve_valve_coil(str(valve_id))
        if coil is None:
            return {"success": False, "error": f"Unknown valve_id: {valve_id}"}
        return await self._execute_set_coil(
            {"coil": coil, "value": params.get("value", False)}
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

    async def execute_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a 4In8Out command."""
        if self._module is None:
            return {"success": False, "error": "Not connected to 4In8Out"}
        try:
            if command == "set_coil":
                return await self._execute_set_coil(params)
            if command == "set_valve":
                return await self._execute_set_valve(params)
            if command == "all_outputs_off":
                return await self._execute_all_outputs_off()
            if command == "read_io_snapshot":
                return await self._execute_read_io_snapshot()
            return {"success": False, "error": f"Unknown command: {command}"}
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"4In8Out command timed out after {self.config.timeout:.1f}s",
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @classmethod
    def get_capabilities(cls) -> dict[str, Any]:
        """Return 4In8Out plugin capabilities."""
        from oqlos.hardware.modbus_io_catalog import VALVE_COIL_MAP

        capabilities = super().get_capabilities()
        capabilities.update({
            "supported_commands": [
                "set_coil",
                "set_valve",
                "all_outputs_off",
                "read_io_snapshot",
            ],
            "valve_mapping": dict(VALVE_COIL_MAP),
            "outputs": OUTPUT_COUNT,
            "inputs": INPUT_COUNT,
            "configuration_schema": {
                "connection_type": {"type": "string", "enum": ["i2c"], "default": "i2c"},
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
                    },
                },
            },
        })
        return capabilities
