from __future__ import annotations

import asyncio
import threading

from oqlos.core._firmware_executor import FirmwareExecutor
from oqlos.core.base import StepStatus
from oqlos.models.dsl_models import CqlAction


class _Vars:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def interpolate(self, value: object) -> str:
        return str(value)

    def set(self, key: str, value: object) -> None:
        self.values[key] = value


class _Out:
    def __init__(self) -> None:
        self.steps: list[tuple[str, str]] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def step(self, icon: str, message: str) -> None:
        self.steps.append((icon, message))

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


class _Normalizer:
    def normalize_pump_power(self, value: object) -> float:
        return float(value)


class _AsyncGateway:
    def __init__(self, pump_result: dict[str, object] | None = None) -> None:
        self.pump_result = pump_result or {"success": True}
        self.calls: list[tuple[object, ...]] = []

    async def set_pump(self, power_pct: float) -> dict[str, object]:
        self.calls.append(("pump", power_pct))
        return self.pump_result

    async def set_valve(self, valve_id: str, value: bool) -> bool:
        self.calls.append(("valve", valve_id, value))
        return True

    async def set_lung(self) -> bool:
        self.calls.append(("lung", True))
        return True


def _executor(
    gateway: _AsyncGateway,
    vars_store: _Vars | None = None,
    out: _Out | None = None,
) -> FirmwareExecutor:
    return FirmwareExecutor(
        mode="execute",
        gateway=gateway,
        vars_store=vars_store or _Vars(),
        output_handler=out or _Out(),
        normalizer=_Normalizer(),
    )


def test_plugin_action_awaits_async_pump_gateway() -> None:
    vars_store = _Vars()
    out = _Out()
    gateway = _AsyncGateway()
    executor = _executor(gateway, vars_store, out)

    status = executor.execute_firmware_action(
        CqlAction(kind="action", target="pump", method="set", args="25")
    )

    assert status is StepStatus.PASSED
    assert gateway.calls == [("pump", 25.0)]
    assert vars_store.values["pump"] == "25"
    assert out.errors == []


def test_plugin_action_treats_failed_pump_result_as_failure() -> None:
    out = _Out()
    gateway = _AsyncGateway({"success": False, "error": "driver refused command"})
    executor = _executor(gateway, out=out)

    status = executor.execute_firmware_action(
        CqlAction(kind="action", target="pump", method="set", args="25")
    )

    assert status is StepStatus.FAILED
    assert gateway.calls == [("pump", 25.0)]
    assert out.errors == ["pump.set FAILED: plugin error"]


def test_plugin_action_uses_gateway_runtime_loop_from_worker_thread() -> None:
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    def _run_loop() -> None:
        asyncio.set_event_loop(loop)
        ready.set()
        loop.run_forever()

    thread = threading.Thread(target=_run_loop, daemon=True)
    thread.start()
    ready.wait(timeout=2)

    gateway = _AsyncGateway()
    gateway._runtime_loop = loop
    executor = _executor(gateway)
    try:
        status = executor.execute_firmware_action(
            CqlAction(kind="action", target="pump", method="set", args="15")
        )
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)
        loop.close()

    assert status is StepStatus.PASSED
    assert gateway.calls == [("pump", 15.0)]
