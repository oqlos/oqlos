"""
Firmware and plugin gateway execution for the OQL interpreter.

Handles hardware action execution via plugin gateway or legacy firmware adapter.
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from oqlos.core.base import StepStatus
    from oqlos.hardware.plugin_gateway import PluginHardwareGateway
    from oqlos.models.dsl_models import OqlAction


def _load_peripheral_map():
    from oqlos.hardware.firmware_adapter import _PERIPHERAL_MAP

    return _PERIPHERAL_MAP


def _plugin_gateway_cls():
    from oqlos.hardware.plugin_gateway import PluginHardwareGateway

    return PluginHardwareGateway


class FirmwareExecutor:
    """Executes hardware actions via plugin gateway or legacy firmware."""

    # Mapping from peripheral family to normalizer method name
    _PERIPHERAL_NORMALIZER_METHODS: dict[str, str] = {
        "pump": "normalize_pump_power",
        "valve": "normalize_valve_value",
        "lung": "normalize_lung_value",
    }

    def __init__(
        self,
        mode: str = "dry-run",
        firmware_url: str = "http://localhost:8202",
        use_plugin_gateway: bool = True,
        vars_store: Any = None,
        output_handler: Any = None,
        normalizer: Any = None,
        gateway: "PluginHardwareGateway | None" = None,
        on_sensors_observed: Callable[[dict[str, float]], None] | None = None,
    ):
        """
        Initialize firmware executor.

        Args:
            mode: Execution mode (validate, dry-run, execute)
            firmware_url: URL for legacy firmware adapter
            use_plugin_gateway: Whether to use plugin gateway (recommended)
            vars_store: VariableStore for value interpolation and storage
            output_handler: InterpreterOutput for emitting messages
            normalizer: ValueNormalizer for value normalization
            gateway: An already-initialized PluginHardwareGateway to reuse. When
                provided, the executor does NOT construct its own gateway — this
                lets the OQL-over-MQTT agent share the app's singleton gateway so
                the RS485/USB serial ports are not opened twice.
            on_sensors_observed: Optional callback invoked with the raw sensor
                readings whenever they're refreshed from real firmware. This
                package stays dependency-light (no event store here) — callers
                that want an audit trail (e.g. oqlos.core.cqrs.telemetry) inject
                the recording behaviour through this hook instead.
        """
        self.mode = mode
        self._firmware_url = firmware_url
        self._use_plugin_gateway = use_plugin_gateway
        self.vars = vars_store
        self.out = output_handler
        self.normalizer = normalizer
        self._firmware = None
        self._plugin_gateway: Any | None = None
        self._on_sensors_observed = on_sensors_observed

        # Use plugin gateway instead of old hardware system. Prefer an injected,
        # already-initialized gateway over constructing a fresh one.
        if gateway is not None:
            self._plugin_gateway = gateway
            self._use_plugin_gateway = True
        elif use_plugin_gateway:
            self._plugin_gateway = _plugin_gateway_cls()(mode=mode)

    def _get_firmware(self):
        """Lazy-init firmware adapter."""
        if self._firmware is None:
            try:
                from oqlos.hardware.firmware_adapter import FirmwareAdapter
            except ImportError:
                raise RuntimeError(
                    "FirmwareAdapter not available — install oqlos with firmware extras "
                    "or run inside the c2004 monorepo"
                )
            self._firmware = FirmwareAdapter(base_url=self._firmware_url)
        return self._firmware

    @staticmethod
    def _resolve_gateway_result(value: Any, gateway: Any = None) -> Any:
        """Run async gateway calls from the synchronous interpreter path."""
        if not inspect.isawaitable(value):
            return value
        preferred_loop = getattr(gateway, "_runtime_loop", None)
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            if preferred_loop is not None and preferred_loop.is_running():
                return asyncio.run_coroutine_threadsafe(value, preferred_loop).result()
            return asyncio.run(value)

        if (
            preferred_loop is not None
            and preferred_loop.is_running()
            and preferred_loop is not running_loop
        ):
            return asyncio.run_coroutine_threadsafe(value, preferred_loop).result()

        result: dict[str, Any] = {}

        def _runner() -> None:
            try:
                result["value"] = asyncio.run(value)
            except BaseException as exc:  # pragma: no cover - re-raised below
                result["error"] = exc

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()
        if "error" in result:
            raise result["error"]
        return result.get("value")

    @staticmethod
    def _is_success(value: Any) -> bool:
        if isinstance(value, dict):
            return bool(value.get("success", value.get("ok", False)))
        return bool(value)

    @staticmethod
    def resolve_peripheral_id(target: str) -> str | None:
        """Resolve a known target name to a firmware peripheral id."""
        normalized = target.strip().lower().replace(" ", "-").replace("_", "-")
        return _load_peripheral_map().get(normalized)

    def normalize_peripheral_value(self, resolved: str | None, value: str) -> Any:
        """Normalize a DSL value according to the resolved peripheral family."""
        if resolved and self.normalizer:
            for prefix, normalizer_name in self._PERIPHERAL_NORMALIZER_METHODS.items():
                if resolved.startswith(prefix):
                    return getattr(self.normalizer, normalizer_name)(value)
        if self.normalizer:
            return self.normalizer.coerce_generic_peripheral_value(value)
        return value

    def refresh_sensors_from_firmware(self, sensor_values: dict[str, float]) -> None:
        """Read all sensor values from firmware and update local cache."""
        try:
            fw = self._get_firmware()
            readings = fw.read_all_sensors()
            sensor_values.update(readings)
            if self._on_sensors_observed is not None:
                self._on_sensors_observed(readings)
        except Exception:
            pass  # Keep existing mock values on failure

    def execute_firmware_action(
        self,
        act: "OqlAction",
        args: str | None = None,
    ) -> "StepStatus":
        """Execute action using plugin gateway when available, otherwise legacy firmware."""
        if self._use_plugin_gateway and self._plugin_gateway:
            return self._execute_plugin_action(act, args)
        else:
            return self._execute_legacy_firmware_action(act, args)

    def _execute_plugin_action(
        self,
        act: "OqlAction",
        args: str | None = None,
    ) -> "StepStatus":
        """Execute action using the new plugin gateway system."""
        from oqlos.core.base import StepStatus

        target = act.target
        method = act.method
        to_send = args if args is not None else self.vars.interpolate(act.args)

        try:
            # Map DSL targets to plugin commands
            if method in {"set", "off"}:
                # Pump command
                power_pct = (
                    self.normalizer.normalize_pump_power(to_send)
                    if method == "set" and self.normalizer
                    else 0.0
                )
                result = self._resolve_gateway_result(
                    self._plugin_gateway.set_pump(power_pct),
                    self._plugin_gateway,
                )
                success = self._is_success(result)
                if success:
                    self.vars.set(target, to_send)
                    self.out.step("    →", f"{act.target}.{act.method} {to_send}")
                    return StepStatus.PASSED
                else:
                    self.out.error(f"{act.target}.{act.method} FAILED: plugin error")
                    return StepStatus.FAILED

            elif method in {"open", "close"}:
                # Valve command
                value = (method == "open")
                result = self._resolve_gateway_result(
                    self._plugin_gateway.set_valve(target, value),
                    self._plugin_gateway,
                )
                success = self._is_success(result)
                if success:
                    self.vars.set(target, value)
                    self.out.step("    →", f"{act.target}.{act.method} {value}")
                    return StepStatus.PASSED
                else:
                    self.out.error(f"{act.target}.{act.method} FAILED: plugin error")
                    return StepStatus.FAILED

            elif method == "reciprocate":
                # Lung command
                result = self._resolve_gateway_result(
                    self._plugin_gateway.set_lung(),
                    self._plugin_gateway,
                )
                success = self._is_success(result)
                if success:
                    self.out.step("    →", f"{act.target}.{act.method}")
                    return StepStatus.PASSED
                else:
                    self.out.error(f"{act.target}.{act.method} FAILED: plugin error")
                    return StepStatus.FAILED

            else:
                self.out.warn(f"Unknown method {method} for target {target}")
                return StepStatus.PASSED

        except Exception as exc:
            self.out.error(f"Plugin execution error: {exc}")
            return StepStatus.FAILED

    def _execute_legacy_firmware_action(
        self,
        act: "OqlAction",
        args: str | None = None,
    ) -> "StepStatus":
        """Execute action on real/simulated firmware (legacy fallback)."""
        from oqlos.core.base import StepStatus

        to_send = args if args is not None else self.vars.interpolate(act.args)
        res = self._get_firmware().dispatch_action(act.target, act.method, to_send)
        if res.get("ok"):
            self.out.step("    →", f"{act.target}.{act.method} {to_send} ({res.get('detail')})")
            return StepStatus.PASSED
        else:
            self.out.error(f"{act.target}.{act.method} FAILED: {res.get('detail')}")
            return StepStatus.FAILED

    def exec_set_peripheral(self, act: "OqlAction", value: str) -> "StepStatus | None":
        """Execute SET action for a peripheral."""
        from oqlos.core.base import StepStatus

        fw = self._get_firmware()
        resolved = self.resolve_peripheral_id(act.target or "")
        normalized_value = self.normalize_peripheral_value(resolved, value)
        try:
            fw.set_peripheral(act.target or "", normalized_value)
        except Exception as exc:
            self.out.error(str(exc))
            return StepStatus.ERROR

        return None
