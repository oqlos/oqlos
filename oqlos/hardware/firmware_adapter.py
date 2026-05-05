"""
dsl/interpreter/firmware_adapter.py — HTTP bridge: CQL → Firmware Simulator (:8202)

Translates CQL actions into firmware API calls:
  → Pump.off         →  PUT /api/v1/peripherals/pump-main  {"currentValue": 0}
  → Pump.set 5       →  PUT /api/v1/peripherals/pump-main  {"currentValue": 5}
  → Valve.open        →  PUT /api/v1/peripherals/valve-inlet {"currentValue": 1}
  → Valve.close       →  PUT /api/v1/peripherals/valve-inlet {"currentValue": 0}

Also reads sensor values from firmware state for condition evaluation.
"""

from __future__ import annotations

import time
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

from oqlos.config import get_settings


# ── Peripheral name mapping ──────────────────────────────────────────────────
# CQL target names → firmware peripheral IDs
_PERIPHERAL_MAP = {
    "pump": "pump-main",
    "pump-main": "pump-main",
    "pump_main": "pump-main",
    "pompa": "pump-main",
    "pompa 1": "pump-main",
    "pompa 2": "pump-main",
    "pompa-1": "pump-main",
    "pompa-2": "pump-main",
    "pompa-kalibracyjna": "pump-main",
    "pompa-testowa": "pump-main",
    "pompa-próżniowa": "pump-main",
    "pompa-ciśnieniowa": "pump-main",
    "pompa-podciśnieniowa": "pump-main",
    "compressor": "pump-main",
    "sprężarka": "pump-main",
    "valve": "valve-1",
    "valve-inlet": "valve-1",
    "valve_inlet": "valve-1",
    "valve-outlet": "valve-2",
    "valve_outlet": "valve-2",
    "zawór-izolacyjny": "valve-1",
    "zawor-izolacyjny": "valve-1",
    "zawór-wlotowy": "valve-1",
    "zawor-wlotowy": "valve-1",
    "zawór-wylotowy": "valve-2",
    "zawor-wylotowy": "valve-2",
    "nc-sensor": "nc-sensor",
    "nc_sensor": "nc-sensor",
    "pressure-sensor": "pressure-sensor",
    "pressure_sensor": "pressure-sensor",
}

for i in range(1, 15):
    _PERIPHERAL_MAP.setdefault(f"valve-{i}", f"valve-{i}")
    _PERIPHERAL_MAP.setdefault(f"valve_{i}", f"valve-{i}")
    _PERIPHERAL_MAP.setdefault(f"zawór-{i}", f"valve-{i}")
    _PERIPHERAL_MAP.setdefault(f"zawor-{i}", f"valve-{i}")

# Circuit valves (NC/SC/WC) — Polish and English names
for circuit in ("nc", "sc", "wc"):
    _PERIPHERAL_MAP[f"valve-{circuit}"] = f"valve-{circuit}"
    _PERIPHERAL_MAP[f"zawór-{circuit}"] = f"valve-{circuit}"
    _PERIPHERAL_MAP[f"zawor-{circuit}"] = f"valve-{circuit}"

# Conceptual valve names → actual firmware peripheral IDs
_PERIPHERAL_MAP["valve-overpressure"] = "valve-5"
_PERIPHERAL_MAP["zawór-overpressure"] = "valve-5"
_PERIPHERAL_MAP["zawor-overpressure"] = "valve-5"
_PERIPHERAL_MAP["overpressure"] = "valve-5"

# Bottle valve (conceptual — no direct firmware peripheral, map to valve-1)
_PERIPHERAL_MAP["zawór-butli"] = "valve-1"
_PERIPHERAL_MAP["zawor-butli"] = "valve-1"
_PERIPHERAL_MAP["valve-butli"] = "valve-1"
_PERIPHERAL_MAP["bottle-valve"] = "valve-1"

# Artificial lung
_PERIPHERAL_MAP["lung"] = "lung-main"
_PERIPHERAL_MAP["lung-main"] = "lung-main"
_PERIPHERAL_MAP["płuco"] = "lung-main"
_PERIPHERAL_MAP["pluco"] = "lung-main"

# CQL sensor names (AI01, AI02, etc.) → firmware peripheral IDs
_SENSOR_MAP = {
    "AI01": "nc-sensor",
    "ciśnienie-nc": "nc-sensor",
    "cisnienie-nc": "nc-sensor",
    "nadciśnienie": "nc-sensor",
    "nadcisnienie": "nc-sensor",
    "AI02": "sc-sensor",
    "ciśnienie-sc": "sc-sensor",
    "cisnienie-sc": "sc-sensor",
    "AI03": "wc-sensor",
    "ciśnienie-wc": "wc-sensor",
}


class FirmwareAdapter:
    """HTTP bridge between CQL interpreter and firmware simulator."""

    def __init__(self, base_url: str = "http://localhost:8202", timeout: float = 5.0, mock: bool = False):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.mock = mock
        self.lung_motor_url = get_settings().lung_motor_url.rstrip("/")
        self._client: Any = None

    def _get_client(self):
        if self._client is None:
            if httpx is None:
                raise RuntimeError("httpx not installed — pip install httpx")
            self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        return self._client

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def _get_lung_motor_url(self) -> str:
        url = getattr(self, "lung_motor_url", "")
        if url:
            return str(url).rstrip("/")
        try:
            return get_settings().lung_motor_url.rstrip("/")
        except Exception:
            return "http://localhost:8205"

    # ── Health check ─────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if firmware simulator is reachable."""
        try:
            r = self._get_client().get("/api/v1/health")
            return r.status_code == 200
        except Exception:
            return False

    # ── Peripheral control ───────────────────────────────────────────────────

    def _resolve_peripheral(self, target: str) -> str:
        """Resolve CQL target name to firmware peripheral ID."""
        key = target.lower().replace(" ", "-")
        return _PERIPHERAL_MAP.get(key, key)

    @staticmethod
    def _raise_if_rejected(data: Any, context: str) -> None:
        """Raise when a hardware endpoint reports logical failure in JSON."""
        if not isinstance(data, dict):
            return

        message: Any = None
        ok = data.get("ok")
        if isinstance(ok, dict):
            success = ok.get("success")
            if success is False:
                message = ok.get("error") or ok.get("message") or ok.get("detail")
        elif ok is False:
            message = data.get("error") or data.get("message") or data.get("detail")

        if data.get("success") is False:
            message = data.get("error") or data.get("message") or data.get("detail") or message

        status = data.get("status")
        if isinstance(status, str) and status.lower() in {"error", "failed", "failure"}:
            message = data.get("error") or data.get("message") or data.get("detail") or message

        if message:
            raise RuntimeError(f"{context} rejected: {message}")

    def set_peripheral(self, target: str, value: Any) -> dict:
        """Set peripheral value via firmware API.

        Routes pump commands to POST /api/v1/hardware/pump and
        valve commands to POST /api/v1/hardware/valve/{id} so that
        the HardwareGateway actually drives real hardware.
        Falls back to PUT /api/v1/peripherals/{pid} for unknown types.
        """
        import re
        
        def _parse_numeric(val):
            """Extract numeric value from string like '5 l/min' or '10 mbar'."""
            if val is None:
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            # Extract first numeric value from string
            match = re.search(r'[-+]?[0-9]*\.?[0-9]+', str(val))
            return float(match.group()) if match else 0.0
        
        pid = self._resolve_peripheral(target)

        # Route to hardware-specific endpoints for real device control
        if pid.startswith("pump"):
            power = _parse_numeric(value)
            r = self._get_client().post(
                "/api/v1/hardware/pump",
                params={"power_pct": power},
            )
            r.raise_for_status()
            data = r.json()
            self._raise_if_rejected(data, f"{target} ({pid})")
            # Also update peripheral state for UI consistency
            self._get_client().put(
                f"/api/v1/peripherals/{pid}",
                json={"currentValue": value, "targetValue": value},
            )
            return data

        if pid.startswith("valve"):
            bool_value = bool(value) if not isinstance(value, bool) else value
            if isinstance(value, (int, float)):
                bool_value = value != 0
            r = self._get_client().post(
                f"/api/v1/hardware/valve/{pid}",
                params={"value": str(bool_value).lower()},
            )
            r.raise_for_status()
            data = r.json()
            self._raise_if_rejected(data, f"{target} ({pid})")
            # Also update peripheral state for UI consistency
            self._get_client().put(
                f"/api/v1/peripherals/{pid}",
                json={"currentValue": value, "targetValue": value},
            )
            return data

        if pid.startswith("lung"):
            # Lung motor: value > 0 starts reciprocating, 0 stops
            lung_url = self._get_lung_motor_url()
            val_num = _parse_numeric(value)
            cycles = int(val_num) if val_num > 0 else 0
            if cycles > 0:
                payload = {"steps": 500, "speed": 100000, "cycles": cycles, "pause": 0.5}
                try:
                    r = self._get_client().post(
                        "/api/v1/hardware/lung",
                        params=payload,
                    )
                    r.raise_for_status()
                    data = r.json()
                    self._raise_if_rejected(data, f"{target} ({pid})")
                    return data
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code != 404:
                        raise
                direct = httpx.Client(base_url=lung_url, timeout=self.timeout)
                try:
                    r = direct.post("/api/reciprocate", json=payload)
                    r.raise_for_status()
                    data = r.json()
                    self._raise_if_rejected(data, f"{target} ({pid})")
                    return data
                finally:
                    direct.close()

            try:
                r = self._get_client().post("/api/v1/hardware/lung/stop")
                r.raise_for_status()
                data = r.json()
                self._raise_if_rejected(data, f"{target} ({pid})")
                return data
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise

            direct = httpx.Client(base_url=lung_url, timeout=self.timeout)
            try:
                r = direct.post("/api/stop")
                r.raise_for_status()
                data = r.json()
                self._raise_if_rejected(data, f"{target} ({pid})")
                return data
            finally:
                direct.close()

        # Fallback: generic peripheral update (state only)
        r = self._get_client().put(
            f"/api/v1/peripherals/{pid}",
            json={"currentValue": value, "targetValue": value},
        )
        r.raise_for_status()
        data = r.json()
        self._raise_if_rejected(data, f"{target} ({pid})")
        return data

    def pump_off(self, target: str = "pump") -> dict:
        return self.set_peripheral(target, 0)

    def pump_set(self, target: str, value: float) -> dict:
        return self.set_peripheral(target, value)

    def valve_open(self, target: str = "valve") -> dict:
        return self.set_peripheral(target, 1)

    def valve_close(self, target: str = "valve") -> dict:
        return self.set_peripheral(target, 0)

    def reset_peripherals(self) -> dict:
        r = self._get_client().post("/api/v1/peripherals/reset")
        r.raise_for_status()
        return r.json()

    # ── Sensor reading ───────────────────────────────────────────────────────

    def read_state(self) -> dict:
        """Read full firmware state."""
        r = self._get_client().get("/api/v1/state")
        r.raise_for_status()
        return r.json()

    def read_sensor(self, sensor_name: str) -> float:
        """Read a sensor value by CQL name (AI01, AI02, etc.)."""
        pid = _SENSOR_MAP.get(sensor_name, sensor_name.lower())
        try:
            r = self._get_client().get(f"/api/v1/hardware/sensor/{pid}")
            r.raise_for_status()
            return float(r.json().get("value", 0.0))
        except Exception:
            # Fallback to state endpoint
            state = self.read_state()
            peripherals = state.get("peripherals", state)
            if isinstance(peripherals, dict):
                p = peripherals.get(pid, {})
                if isinstance(p, dict):
                    return float(p.get("currentValue", 0.0))
            return 0.0

    def read_all_sensors(self) -> dict[str, float]:
        """Read all known sensor values."""
        result: dict[str, float] = {}
        for cql_name, pid in _SENSOR_MAP.items():
            try:
                r = self._get_client().get(f"/api/v1/hardware/sensor/{pid}")
                r.raise_for_status()
                result[cql_name] = float(r.json().get("value", 0.0))
            except Exception:
                result[cql_name] = 0.0
        return result

    # ── CQL action keywords ─────────────────────────────────────────────────

    _ACTION_KEYWORDS = {
        "off", "on", "set", "open", "close", "start", "stop", "reset",
        "read", "confirm", "potwierdź", "potwierdz", "wyłącz", "wylacz",
        "włącz", "wlacz", "ustaw", "otwórz", "otworz", "zamknij",
        "zmierz", "sprawdź", "sprawdz", "odczytaj", "wyzeruj",
    }

    # ── CQL action dispatch ──────────────────────────────────────────────────

    def _resolve_dispatch_target(self, target: str, method: str, args: str) -> tuple[str, str, str]:
        """Resolve peripheral_id, effective method, and remaining args.

        When 'method' isn't an action keyword (e.g. Valve.6), combine
        target-method into a peripheral identifier and promote args.
        """
        import re as _re
        method_lower = method.lower().strip()
        target_lower = target.lower().strip()
        args_stripped = args.strip()

        if method_lower not in self._ACTION_KEYWORDS or _re.match(r'^\d+$', method_lower):
            combined = f"{target_lower}-{method_lower}"
            self._resolve_peripheral(combined)
            return combined, args_stripped.lower() if args_stripped else "on", ""

        return target_lower, method_lower, args_stripped

    # ── Action Handlers ──────────────────────────────────────────────────────

    def _handle_lung_action(self, target: str, peripheral: str, method: str, args: str) -> dict:
        if method in {"off", "stop", "wyłącz", "wylacz", "zamknij", "close"}:
            data = self.set_peripheral(peripheral, 0)
            return {"ok": True, "detail": f"{target}.stop → lung stopped", "data": data}
        cycles = _parse_numeric(args) if args.strip() else 5
        data = self.set_peripheral(peripheral, cycles)
        return {"ok": True, "detail": f"{target}.reciprocate → {int(cycles)} cycles", "data": data}

    def _handle_valve_action(self, target: str, peripheral: str, method: str, args: str) -> dict:
        if method in {"off", "wyłącz", "wylacz", "stop", "zamknij", "close"}:
            data = self.valve_close(peripheral)
            return {"ok": True, "detail": f"{target}.close → 0", "data": data}
        if method in {"open", "otwórz", "otworz"}:
            data = self.valve_open(peripheral)
            return {"ok": True, "detail": f"{target}.open → 1", "data": data}
        # default to open/on
        data = self.valve_open(peripheral)
        return {"ok": True, "detail": f"{target}.open (default) → 1", "data": data}

    def _handle_pump_action(self, target: str, peripheral: str, method: str, args: str) -> dict:
        if method in {"off", "wyłącz", "wylacz", "stop"}:
            data = self.pump_off(peripheral)
            return {"ok": True, "detail": f"{target}.off → 0", "data": data}
        val = _parse_numeric(args) if args.strip() else 1.0
        data = self.pump_set(peripheral, val)
        return {"ok": True, "detail": f"{target}.set → {val}", "data": data}

    def _handle_common_action(self, target: str, method: str, args: str) -> dict | None:
        if method in {"reset", "wyzeruj"}:
            data = self.reset_peripherals()
            return {"ok": True, "detail": "reset all", "data": data}
        if method in {"confirm", "potwierdź", "potwierdz"}:
            return {"ok": True, "detail": f"Operator confirmed: {args}", "data": {}}
        return None

    def _execute_method(self, target: str, peripheral_target: str, method_lower: str, args: str) -> dict:
        """Execute the resolved method on the target peripheral using a dispatch table."""
        common = self._handle_common_action(target, method_lower, args)
        if common:
            return common

        pid = self._resolve_peripheral(peripheral_target)
        
        # Sensor reading
        if method_lower in {"read", "zmierz", "sprawdź", "sprawdz", "odczytaj"}:
            val = self.read_sensor(peripheral_target)
            return {"ok": True, "detail": f"{target} = {val}", "data": {"value": val}}

        # Type-specific dispatch
        if pid.startswith("lung"):
            return self._handle_lung_action(target, pid, method_lower, args)
        if pid.startswith("valve"):
            return self._handle_valve_action(target, pid, method_lower, args)
        if pid.startswith("pump"):
            return self._handle_pump_action(target, pid, method_lower, args)

        # Fallback for generic peripherals
        try:
            val = _parse_numeric(args) if args.strip() else 1
            data = self.set_peripheral(pid, val)
            return {"ok": True, "detail": f"{target}.{method_lower} → {val}", "data": data}
        except Exception as e:
            return {"ok": False, "detail": f"Unknown method or error: {target}.{method_lower} ({e})", "data": {}}

    def dispatch_action(self, target: str, method: str, args: str = "") -> dict:
        """Dispatch a CQL action (→ Target.method args) to firmware.

        Handles patterns like:
          → Pump.off           target=Pump, method=off
          → Valve.6 on         target=Valve, method=6 → reinterpreted as target=valve-6, method=on
          → BO06.on            target=BO06, method=on

        Returns:
            {"ok": True/False, "detail": str, "data": any}
        """
        peripheral_target, effective_method, remaining_args = self._resolve_dispatch_target(target, method, args)

        try:
            return self._execute_method(target, peripheral_target, effective_method, remaining_args or args)
        except Exception as e:
            return {"ok": False, "detail": str(e), "data": {}}


def _parse_numeric(s: str) -> float:
    """Parse numeric value from CQL args like '5l', '7.0 mbar', '100%'."""
    import re
    m = re.search(r"[-+]?\d*\.?\d+", s)
    return float(m.group()) if m else 0.0
