# firmware/services/hardware_gateway.py
"""Hardware gateway — routes DSL step actions to real hardware services.

Reads config from env vars:
  HARDWARE_MODE    = mock | real          (default: mock)
  PIADC_URL        = http://host:8080     (piadc ADS1115 service)
  MOTOR_URL        = http://host:8001     (rpi-motor-tic249 service)
    MODBUS_SERIAL_PORT = /dev/ttyACM1       (preferred RTU serial port)
    MODBUS_BAUD      = 19200                (preferred RTU baud rate)
    MODBUS_PARITY    = N                    (preferred parity, 8N1 by default)
    MODBUS_HOST      = host                 (optional Modbus TCP fallback)
    MODBUS_PORT      = 502                  (Modbus TCP port)

Channel mapping (piadc ADS1115 channels → sensor IDs):
  channel 0 → nc-sensor  (negative-circuit, mbar)
  channel 1 → sc-sensor  (smoke-circuit, bar)
  channel 2 → wc-sensor  (water-circuit, bar)
  channel 3 → spare

Valve mapping (valve-N id → Modbus coil address):
    valve-1 … valve-8   → coil 0 … 7
    valve-nc            → coil 0
    valve-sc            → coil 1
    valve-wc            → coil 2
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from oqlos.hardware.discovery import (
    DEFAULT_MODBUS_BAUD,
    DEFAULT_MODBUS_PARITY,
    DEFAULT_MODBUS_SERIAL,
    probe_waveshare_modbus,
)

logger = logging.getLogger(__name__)

_HARDWARE_MODE = os.getenv("HARDWARE_MODE", "mock").lower()
_PIADC_URL = os.getenv("PIADC_URL", "http://localhost:8080")
_MOTOR_URL = os.getenv("MOTOR_URL", "http://localhost:8001")
_MODBUS_HOST = os.getenv("MODBUS_HOST", "localhost")
_MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))
_MODBUS_SERIAL = os.getenv("MODBUS_SERIAL_PORT", DEFAULT_MODBUS_SERIAL)
_MODBUS_BAUD = int(os.getenv("MODBUS_BAUD", str(DEFAULT_MODBUS_BAUD)))
_MODBUS_PARITY = os.getenv("MODBUS_PARITY", DEFAULT_MODBUS_PARITY).upper()

_SENSOR_CHANNEL_MAP: dict[str, int] = {
    "nc-sensor": 0,
    "sc-sensor": 1,
    "wc-sensor": 2,
}

# Valve → DO channel mapping (Waveshare Modbus RTU IO 8CH: DO1–DO8 = coil 0–7)
_VALVE_COIL_MAP: dict[str, int] = {
    **{f"valve-{i}": i - 1 for i in range(1, 9)},  # valve-1→DO1(0) … valve-8→DO8(7)
    "valve-nc": 0,   # NC valve on DO1
    "valve-sc": 1,   # SC valve on DO2
    "valve-wc": 2,   # WC valve on DO3
}

_TIMEOUT = httpx.Timeout(5.0)


class _PiAdcAdapter:
    """Reads pressure / analog sensors via piadc REST API (ADS1115)."""

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    async def read_channel(self, channel: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{self._base}/read/{channel}")
            resp.raise_for_status()
            return resp.json()

    async def read_sensor(self, sensor_id: str) -> float | None:
        channel = _SENSOR_CHANNEL_MAP.get(sensor_id)
        if channel is None:
            logger.warning("Unknown sensor '%s', no ADC channel mapping", sensor_id)
            return None
        data = await self.read_channel(channel)
        return data.get("voltage")


class _TicMotorAdapter:
    """Controls the artificial-lung stepper motor via rpi-motor-tic249 REST API."""

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    async def set_speed(self, power_pct: float) -> dict[str, Any]:
        """Map 0–100% pump power to motor reciprocation speed."""
        if power_pct <= 0:
            return await self._stop()
        speed = int(power_pct / 100 * 5000)
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base}/api/reciprocate",
                json={"speed": speed, "cycles": 0},
            )
            resp.raise_for_status()
            return resp.json()

    async def _stop(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(f"{self._base}/api/stop")
            resp.raise_for_status()
            return resp.json()

    async def status(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{self._base}/api/status")
            resp.raise_for_status()
            return resp.json()


class _ModbusAdapter:
    """Controls valves via Modbus RTU over RS485 (Waveshare Modbus RTU IO 8CH).

    Primary mode: serial RTU (pymodbus ModbusSerialClient).
    Fallback: Modbus TCP if MODBUS_HOST is set and serial unavailable.
    Stub: logging only if neither pymodbus nor serial available.
    """

    def __init__(self, serial_port: str, baudrate: int, parity: str, host: str, port: int) -> None:
        self._discovery = probe_waveshare_modbus(
            preferred_port=serial_port,
            preferred_baud=baudrate,
            preferred_parity=parity,
        )
        self._serial_port = str(self._discovery.get("serial_port") or serial_port)
        self._baudrate = int(self._discovery.get("baudrate") or baudrate)
        self._parity = str(self._discovery.get("parity") or parity).upper()
        self._host = host
        self._port = port
        self._client: Any = None
        self._mode = "stub"
        try:
            from pymodbus.client import ModbusSerialClient  # type: ignore
            self._client = ModbusSerialClient(
                port=self._serial_port,
                baudrate=self._baudrate,
                stopbits=1,
                bytesize=8,
                parity=self._parity,
                timeout=2,
            )
            self._mode = "rtu"
            logger.info(
                "pymodbus RTU — serial %s @ %d 8%s1",
                self._serial_port,
                self._baudrate,
                self._parity,
            )
        except (ImportError, Exception):
            try:
                from pymodbus.client import AsyncModbusTcpClient  # type: ignore
                self._client = AsyncModbusTcpClient(host=host, port=port)
                self._mode = "tcp"
                logger.info("pymodbus TCP fallback — %s:%d", host, port)
            except ImportError:
                logger.warning(
                    "pymodbus not installed — valve commands will be logged only. "
                    "Install with: pip install pymodbus"
                )

    async def set_coil(self, coil: int, value: bool) -> bool:
        if self._client is None:
            logger.info("[MODBUS STUB] coil %d → %s", coil, value)
            return True
        if self._mode == "rtu":
            # Synchronous ModbusSerialClient (pymodbus 3.x)
            try:
                if not self._client.connected:
                    self._client.connect()
                # Waveshare: write single coil (func 05), 0xFF00=ON, 0x0000=OFF
                result = self._client.write_coil(address=coil, value=value, device_id=1)
                ok = hasattr(result, 'function_code') and not getattr(result, 'isError', lambda: True)()
                if not ok:
                    logger.error("Modbus RTU write_coil(%d, %s) failed: %s", coil, value, result)
                return ok
            except Exception as exc:
                logger.error("Modbus RTU error: %s", exc)
                return False
        else:
            # TCP fallback (async)
            await self._client.connect()
            result = await self._client.write_coil(coil, value)
            await self._client.close()
            ok = not result.isError()
            if not ok:
                logger.error("Modbus TCP write_coil(%d, %s) failed: %s", coil, value, result)
            return ok

    async def set_valve(self, valve_id: str, value: bool) -> bool:
        coil = _VALVE_COIL_MAP.get(valve_id)
        if coil is None:
            logger.warning("No Modbus coil mapping for valve '%s'", valve_id)
            return False
        return await self.set_coil(coil, value)


class HardwareGateway:
    """Single entry-point for all physical hardware I/O.

    In *mock* mode every call is a no-op that logs the intended action.
    In *real* mode it calls the actual hardware services (piadc / tic249 / modbus).
    """

    def __init__(self) -> None:
        self.mode = _HARDWARE_MODE
        self._piadc = _PiAdcAdapter(_PIADC_URL)
        self._motor = _TicMotorAdapter(_MOTOR_URL)
        self._modbus = _ModbusAdapter(_MODBUS_SERIAL, _MODBUS_BAUD, _MODBUS_PARITY, _MODBUS_HOST, _MODBUS_PORT)
        logger.info(
            "HardwareGateway init: mode=%s piadc=%s motor=%s modbus=%s@%d 8%s1 (tcp-fallback=%s:%d)",
            self.mode,
            _PIADC_URL,
            _MOTOR_URL,
            self._modbus._serial_port,
            self._modbus._baudrate,
            self._modbus._parity,
            _MODBUS_HOST,
            _MODBUS_PORT,
        )

    @property
    def is_real(self) -> bool:
        return self.mode == "real"

    async def set_valve(self, valve_id: str, value: bool) -> bool:
        if not self.is_real:
            logger.info("[HW mock] SET_VALVE %s → %s", valve_id, value)
            return True
        try:
            return await self._modbus.set_valve(valve_id, value)
        except Exception as exc:
            logger.error("HardwareGateway.set_valve error: %s", exc)
            return False

    async def set_pump(self, power_pct: float) -> bool:
        if not self.is_real:
            logger.info("[HW mock] SET_PUMP %.1f%%", power_pct)
            return True
        try:
            await self._motor.set_speed(power_pct)
            return True
        except Exception as exc:
            logger.error("HardwareGateway.set_pump error: %s", exc)
            return False

    async def read_sensor(self, sensor_id: str) -> float | None:
        if not self.is_real:
            logger.info("[HW mock] READ_SENSOR %s → None", sensor_id)
            return None
        try:
            return await self._piadc.read_sensor(sensor_id)
        except Exception as exc:
            logger.error("HardwareGateway.read_sensor error: %s", exc)
            return None

    async def health(self) -> dict[str, Any]:
        """Return connectivity status for all hardware services."""
        result: dict[str, Any] = {"mode": self.mode}
        if not self.is_real:
            result["note"] = "mock mode — no hardware calls"
            return result

        for name, url in [("piadc", _PIADC_URL), ("motor", _MOTOR_URL)]:
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
                    r = await c.get(f"{url}/health")
                result[name] = "ok" if r.status_code < 300 else f"http {r.status_code}"
            except Exception as exc:
                result[name] = f"error: {exc}"

        result["modbus"] = (
            f"{self._modbus._serial_port}@{self._modbus._baudrate} 8{self._modbus._parity}1 "
            f"(mode={self._modbus._mode})"
        )
        return result
