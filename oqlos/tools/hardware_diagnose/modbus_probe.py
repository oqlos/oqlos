"""Direct Modbus RTU probe utility used outside the running OqlOS gateway."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any


READ_METHODS = {
    "read_coils": "read_coils",
    "coils": "read_coils",
    "read_discrete_inputs": "read_discrete_inputs",
    "discrete_inputs": "read_discrete_inputs",
    "read_holding_registers": "read_holding_registers",
    "holding_registers": "read_holding_registers",
    "read_input_registers": "read_input_registers",
    "input_registers": "read_input_registers",
}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def _env_int_list(name: str, fallback: list[int]) -> list[int]:
    value = os.environ.get(name)
    if not value:
        return fallback
    result: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if item:
            result.append(int(item))
    return result or fallback


def _env_count_list(name: str, fallback: list[int]) -> list[int]:
    result = _env_int_list(name, fallback)
    return [max(1, item) for item in result]


def _env_str_list(name: str, fallback: list[str]) -> list[str]:
    value = os.environ.get(name)
    if not value:
        return fallback
    result = _split_values(value)
    return result or fallback


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value else default


def _split_values(values: str | list[str]) -> list[str]:
    if isinstance(values, str):
        values = [values]
    result: list[str] = []
    for value in values:
        result.extend(item.strip() for item in value.split(",") if item.strip())
    return result


def _arg_str_list(values: list[str] | None, fallback: list[str]) -> list[str]:
    return _split_values(values) if values else fallback


def _arg_int_list(values: list[str] | None, fallback: list[int]) -> list[int]:
    return [int(item) for item in _split_values(values)] if values else fallback


def _arg_count_list(values: list[str] | None, fallback: list[int]) -> list[int]:
    return [max(1, item) for item in _arg_int_list(values, fallback)] if values else fallback


def _serials_from_env() -> list[str]:
    return [
        item.strip()
        for item in os.environ.get("MODBUS_SERIAL", "/dev/ttyACM1").split(",")
        if item.strip()
    ]


def add_modbus_probe_arguments(parser: argparse.ArgumentParser) -> None:
    """Add direct probe arguments to an argparse parser."""
    parser.add_argument("--serial", "--serials", dest="serials", action="append",
                        help="Serial port(s), comma-separated or repeated")
    parser.add_argument("--baud", "--bauds", dest="baudrates", action="append",
                        help="Baudrate(s), comma-separated or repeated")
    parser.add_argument("--parity", "--parities", dest="parities", action="append",
                        help="Parity value(s), usually N/E/O")
    parser.add_argument("--device-id", "--device-ids", dest="device_ids", action="append",
                        help="Modbus device id(s), comma-separated or repeated")
    parser.add_argument("--function", "--functions", dest="functions", action="append",
                        help="Read function(s), e.g. read_coils or holding_registers")
    parser.add_argument("--address", "--addresses", dest="addresses", action="append",
                        help="Start address(es), comma-separated or repeated")
    parser.add_argument("--count", "--counts", dest="counts", action="append",
                        help="Register/coil count(s), comma-separated or repeated")
    parser.add_argument("--timeout", type=float, default=None,
                        help="Per-attempt timeout in seconds")


def probe_options_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Build probe options from CLI args, falling back to the legacy MODBUS_* env."""
    return {
        "serials": _arg_str_list(getattr(args, "serials", None), _serials_from_env()),
        "baudrates": _arg_int_list(
            getattr(args, "baudrates", None),
            _env_int_list("MODBUS_BAUDS", [_env_int("MODBUS_BAUD", 19200)]),
        ),
        "parities": _arg_str_list(
            getattr(args, "parities", None),
            _env_str_list("MODBUS_PARITIES", [os.environ.get("MODBUS_PARITY", "N")]),
        ),
        "device_ids": _arg_int_list(
            getattr(args, "device_ids", None),
            _env_int_list("MODBUS_DEVICE_IDS", [_env_int("MODBUS_DEVICE_ID", 1)]),
        ),
        "functions": _arg_str_list(
            getattr(args, "functions", None),
            _env_str_list("MODBUS_FUNCTIONS", ["read_coils"]),
        ),
        "addresses": _arg_int_list(
            getattr(args, "addresses", None),
            _env_int_list("MODBUS_ADDRESSES", [0]),
        ),
        "counts": _arg_count_list(
            getattr(args, "counts", None),
            _env_count_list("MODBUS_COUNTS", [_env_int("MODBUS_COUNT", 1)]),
        ),
        "timeout": (
            args.timeout
            if getattr(args, "timeout", None) is not None
            else _env_float("MODBUS_PROBE_TIMEOUT", 0.5)
        ),
    }


def run_modbus_probe_from_args(args: argparse.Namespace) -> dict[str, Any]:
    """Run the direct Modbus probe using CLI args with env fallback."""
    return run_modbus_probe(**probe_options_from_args(args))


def run_modbus_probe_from_env() -> dict[str, Any]:
    """Run the direct Modbus probe using the legacy MODBUS_* environment contract."""
    return run_modbus_probe(
        serials=_serials_from_env(),
        baudrates=_env_int_list("MODBUS_BAUDS", [_env_int("MODBUS_BAUD", 19200)]),
        parities=_env_str_list("MODBUS_PARITIES", [os.environ.get("MODBUS_PARITY", "N")]),
        device_ids=_env_int_list("MODBUS_DEVICE_IDS", [_env_int("MODBUS_DEVICE_ID", 1)]),
        functions=_env_str_list("MODBUS_FUNCTIONS", ["read_coils"]),
        addresses=_env_int_list("MODBUS_ADDRESSES", [0]),
        counts=_env_count_list("MODBUS_COUNTS", [_env_int("MODBUS_COUNT", 1)]),
        timeout=_env_float("MODBUS_PROBE_TIMEOUT", 0.5),
    )


def run_modbus_probe(
    *,
    serials: list[str],
    baudrates: list[int],
    parities: list[str],
    device_ids: list[int],
    functions: list[str],
    addresses: list[int],
    counts: list[int],
    timeout: float,
) -> dict[str, Any]:
    """Try all requested Modbus RTU read combinations and return JSON-safe results."""
    try:
        from pymodbus.client import ModbusSerialClient  # type: ignore
    except Exception as exc:
        return {"ok": False, "error": f"pymodbus import failed: {exc}"}

    results: list[dict[str, Any]] = []
    ok = False

    for serial_port in serials:
        for baudrate in baudrates:
            for parity in parities:
                for device_id in device_ids:
                    for function in functions:
                        method_name = READ_METHODS.get(function)
                        if not method_name:
                            results.append({
                                "serial_port": serial_port,
                                "baudrate": baudrate,
                                "parity": parity,
                                "device_id": device_id,
                                "function": function,
                                "ok": False,
                                "error": "unsupported read function",
                            })
                            continue

                        for address in addresses:
                            for count in counts:
                                client: Any = None
                                item: dict[str, Any] = {
                                    "serial_port": serial_port,
                                    "baudrate": baudrate,
                                    "parity": parity,
                                    "device_id": device_id,
                                    "function": method_name,
                                    "address": address,
                                    "count": count,
                                    "timeout": timeout,
                                }

                                try:
                                    client = ModbusSerialClient(
                                        port=serial_port,
                                        baudrate=baudrate,
                                        stopbits=1,
                                        bytesize=8,
                                        parity=parity,
                                        timeout=timeout,
                                    )
                                    item["open"] = bool(client.connect())
                                    if not item["open"]:
                                        item["ok"] = False
                                        item["error"] = "serial connection failed"
                                        continue

                                    method = getattr(client, method_name)
                                    result = method(address=address, count=count, device_id=device_id)
                                    item["response"] = str(result)
                                    item["ok"] = bool(result and not result.isError())
                                    ok = ok or item["ok"]
                                except Exception as exc:
                                    item["ok"] = False
                                    item["error"] = repr(exc)
                                finally:
                                    if client is not None:
                                        try:
                                            client.close()
                                        except Exception:
                                            pass
                                    results.append(item)

    return {"ok": ok, "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe Modbus RTU directly outside OqlOS runtime")
    add_modbus_probe_arguments(parser)
    args = parser.parse_args(argv)

    result = run_modbus_probe_from_args(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
