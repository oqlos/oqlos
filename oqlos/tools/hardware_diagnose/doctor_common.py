"""Shared types and helpers for hardware doctor analysis."""

from __future__ import annotations

from typing import Any

Issue = dict[str, Any]

_HEALTH_KEYS_BY_ADAPTER = {
    "modbus-adc": ("modbus-adc",),
    "piadc": ("modbus-adc", "piadc"),
    "motor-dri0050": ("motor-dri0050", "motor"),
    "motor-tic249": ("motor-tic249", "lung"),
    "modbus-io": ("modbus-io", "modbus"),
    "io-m5-4in8out": ("io-m5-4in8out", "m5-4in8out"),
}

LOCAL_FIRMWARE_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


def add_issue(
    issues: list[Issue],
    *,
    severity: str,
    code: str,
    message: str,
    repair: dict[str, Any] | None = None,
) -> None:
    issue: Issue = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if repair:
        issue["repair"] = repair
    issues.append(issue)


def plugin_config(config: dict[str, Any], plugin_id: str) -> dict[str, Any] | None:
    plugins = config.get("plugins")
    if not isinstance(plugins, dict):
        return None
    plugin = plugins.get(plugin_id)
    return plugin if isinstance(plugin, dict) else None


def modbus_config(config: dict[str, Any]) -> dict[str, Any] | None:
    return plugin_config(config, "modbus-io")


def modbus_adc_config(config: dict[str, Any]) -> dict[str, Any] | None:
    return plugin_config(config, "modbus-adc")


def collect_repairs(issues: list[Issue]) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for issue in issues:
        repair = issue.get("repair")
        if not isinstance(repair, dict):
            continue
        repair_id = str(repair.get("id", ""))
        if not repair_id or repair_id in seen:
            continue
        seen.add(repair_id)
        repairs.append({"applied": False, **repair})
    return repairs
