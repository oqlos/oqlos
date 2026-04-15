"""Hardware calibration test runner."""

from __future__ import annotations

import time


def run_calibration_test(url: str = "http://localhost:8202") -> dict:
    """Run calibration test for all hardware components.

    Returns:
        dict with keys: timestamp, tests, passed, failed, errors.
        Each entry in 'tests': {name, passed, details}.
    """
    results: dict = {
        "timestamp": time.time(),
        "tests": [],
        "passed": 0,
        "failed": 0,
        "errors": [],
    }

    def _log(name: str, passed: bool, details: str = "") -> None:
        results["tests"].append({"name": name, "passed": passed, "details": details})
        if passed:
            results["passed"] += 1
        else:
            results["failed"] += 1
            results["errors"].append(f"{name}: {details}")

    try:
        import httpx
        with httpx.Client() as client:
            _calibrate_pump(client, url, _log)
            _calibrate_valves(client, url, _log)
            _calibrate_sensors(client, url, _log)
    except Exception as e:
        results["errors"].append(f"Calibration error: {e}")

    return results


def _calibrate_pump(client, url: str, log) -> None:
    """Test pump response time."""
    import time as _time
    try:
        start = _time.time()
        r = client.post(f"{url}/api/v1/hardware/pump", params={"power_pct": 10}, timeout=2.0)
        response_ms = (_time.time() - start) * 1000
        if r.status_code == 200:
            log("pump_response", True, f"Response: {response_ms:.1f}ms")
            client.post(f"{url}/api/v1/hardware/pump", params={"power_pct": 0}, timeout=2.0)
        else:
            log("pump_response", False, f"HTTP {r.status_code}")
    except Exception as e:
        log("pump_response", False, str(e))


def _calibrate_valves(client, url: str, log) -> None:
    """Test open/close cycle for NC/SC/WC valves."""
    for valve in ("valve-nc", "valve-sc", "valve-wc"):
        try:
            r = client.post(
                f"{url}/api/v1/hardware/valve/{valve}",
                params={"value": "true"}, timeout=2.0,
            )
            if r.status_code == 200:
                client.post(
                    f"{url}/api/v1/hardware/valve/{valve}",
                    params={"value": "false"}, timeout=2.0,
                )
                log(f"{valve}_calibration", True, "Open/Close OK")
            else:
                log(f"{valve}_calibration", False, f"HTTP {r.status_code}")
        except Exception as e:
            log(f"{valve}_calibration", False, str(e))


def _calibrate_sensors(client, url: str, log) -> None:
    """Verify sensor readings are in plausible range."""
    for sensor in ("nc-sensor", "sc-sensor", "wc-sensor"):
        try:
            r = client.get(f"{url}/api/v1/hardware/sensor/{sensor}", timeout=2.0)
            if r.status_code == 200:
                value = r.json().get("value", 0)
                in_range = -5000 <= float(value) <= 5000
                log(f"{sensor}_reading", in_range,
                    f"Value: {value}" if in_range else f"Out of range: {value}")
            else:
                log(f"{sensor}_reading", False, f"HTTP {r.status_code}")
        except Exception as e:
            log(f"{sensor}_reading", False, str(e))
