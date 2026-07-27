"""Canonical BoardNet Modbus I/O channel catalogue.

The physical DO -> coil mapping used to be repeated in the gateway, plugin and
UI.  Keep the stable electrical identity here and let runtime HUI mappings add
their current logical uses dynamically.
"""

from __future__ import annotations

from typing import Any

MODBUS_IO_COIL_COUNT = 8

VALVE_COIL_MAP: dict[str, int] = {
    **{f"valve-{index}": index - 1 for index in range(1, MODBUS_IO_COIL_COUNT + 1)},
    "valve-nc": 0,
    "valve-sc": 1,
    "valve-wc": 2,
}

COIL_LOGICAL_ALIASES: dict[int, tuple[str, ...]] = {
    address: tuple(
        alias for alias, mapped_address in VALVE_COIL_MAP.items() if mapped_address == address
    )
    for address in range(MODBUS_IO_COIL_COUNT)
}


def resolve_valve_coil(valve_id: str) -> int | None:
    """Resolve a public valve alias to the zero-based Waveshare coil address."""
    return VALVE_COIL_MAP.get(str(valve_id or "").strip().lower().replace("_", "-"))


def _append_use(uses: dict[int, list[dict[str, Any]]], valve_id: str, use: dict[str, Any]) -> None:
    address = resolve_valve_coil(valve_id)
    if address is None:
        return
    uses[address].append({"valve_id": valve_id, **use})


def runtime_coil_uses() -> dict[int, list[dict[str, Any]]]:
    """Collect current HUI hold/button uses from effective configuration."""
    from oqlos.hardware.hui_hold import get_hui_hold_profiles
    from oqlos.hardware.hui_valve import get_hui_valve_specs

    uses: dict[int, list[dict[str, Any]]] = {
        address: [] for address in range(MODBUS_IO_COIL_COUNT)
    }
    for key, profile in get_hui_hold_profiles().items():
        for valve_id in profile.get("valves_on") or ():
            _append_use(
                uses,
                str(valve_id),
                {
                    "kind": "hui_hold",
                    "control": key,
                    "action": "energize while held",
                },
            )
    for key, spec in get_hui_valve_specs().items():
        valve_id = str(spec.get("valve_id") or "")
        _append_use(
            uses,
            valve_id,
            {
                "kind": "hui_button",
                "control": key,
                "action": "on" if bool(spec.get("value")) else "off",
            },
        )
    return uses


def build_coil_catalog(states: list[bool] | None = None) -> list[dict[str, Any]]:
    """Return ordered DO1..DO8 data with electrical identity and runtime uses."""
    values = list(states or [])
    uses = runtime_coil_uses()
    return [
        {
            "sequence": address + 1,
            "id": f"DO{address + 1}",
            "address": address,
            "address_hex": f"coil:{address}",
            "primary_valve_id": f"valve-{address + 1}",
            "aliases": list(COIL_LOGICAL_ALIASES[address]),
            "uses": uses[address],
            "state": values[address] if address < len(values) else None,
        }
        for address in range(MODBUS_IO_COIL_COUNT)
    ]
