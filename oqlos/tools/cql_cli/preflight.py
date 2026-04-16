"""
Hardware preflight checks for CQL CLI.

Extracted from cql_cli.py to reduce complexity. Original CC=28.
Refactored into smaller, focused functions with CC<10 each.
"""

from __future__ import annotations

import subprocess
import sys
import time

import click
import httpx

from oqlos.tools.cql_cli.utils import output_yaml, resolve_required_adapter
from oqlos.tools.hardware_diagnose.health import check_firmware_health, check_firmware_identify


def ensure_firmware_running(firmware_url: str, *, quiet: bool, yaml_output: bool = False) -> bool:
    """Attempt to start firmware service if it's not available."""
    # First check if already running
    if _is_firmware_running(firmware_url, quiet=quiet, yaml_output=yaml_output):
        return True

    # Not running - try to start it
    return _start_firmware_service(firmware_url, quiet=quiet, yaml_output=yaml_output)


def _is_firmware_running(firmware_url: str, *, quiet: bool, yaml_output: bool) -> bool:
    """Check if firmware is already running."""
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{firmware_url}/health")
            if resp.status_code < 300:
                if not quiet and not yaml_output:
                    click.echo(f"[OK] Firmware already running at {firmware_url}", err=True)
                return True
    except Exception:
        pass
    return False


def _start_firmware_service(firmware_url: str, *, quiet: bool, yaml_output: bool) -> bool:
    """Start the firmware service in background."""
    if not quiet and not yaml_output:
        click.echo(f"[WAIT] Firmware not available at {firmware_url}, attempting to start...", err=True)

    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "oqlos.api.main"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Wait for it to become healthy (max 10 seconds)
        max_wait = 10
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                with httpx.Client(timeout=1.0) as client:
                    resp = client.get(f"{firmware_url}/health")
                    if resp.status_code < 300:
                        if not quiet and not yaml_output:
                            click.echo(f"[OK] Firmware started successfully at {firmware_url}", err=True)
                        return True
            except Exception:
                time.sleep(0.5)

        if not quiet and not yaml_output:
            click.echo(f"[ERROR] Firmware did not start within {max_wait}s", err=True)
        process.terminate()
        return False
    except Exception as exc:
        if not quiet and not yaml_output:
            click.echo(f"[ERROR] Failed to start firmware: {exc}", err=True)
        return False


def check_firmware_state(firmware_url: str, yaml_output: bool, quiet: bool) -> tuple[bool, dict, dict]:
    """
    Check firmware health and identify state.
    Returns (ok, health_data, identify_data) tuple.
    """
    health = check_firmware_health(firmware_url)
    if "error" in health:
        error_msg = f"Hardware preflight failed: firmware health at {firmware_url} is unavailable ({health['error']})"
        _emit_preflight_error(error_msg, yaml_output, quiet)
        return False, health, {}

    if str(health.get("mode", "")).lower() != "real":
        error_msg = f"Hardware preflight failed: firmware mode is {health.get('mode', 'unknown')!r}; real hardware is required"
        _emit_preflight_error(error_msg, yaml_output, quiet)
        return False, health, {}

    identify = check_firmware_identify(firmware_url)
    if "error" in identify:
        error_msg = f"Hardware preflight failed: hardware identify at {firmware_url} is unavailable ({identify['error']})"
        _emit_preflight_error(error_msg, yaml_output, quiet)
        return False, health, identify

    detected = int(identify.get("detected", 0) or 0)
    total = int(identify.get("total", 0) or 0)
    if detected <= 0:
        total_display = total if total else "?"
        error_msg = f"Hardware preflight failed: no hardware adapters detected ({detected}/{total_display})"
        _emit_preflight_error(error_msg, yaml_output, quiet)
        return False, health, identify

    return True, health, identify


def check_required_adapter(
    command: str,
    adapters: list[dict],
    yaml_output: bool,
    quiet: bool
) -> tuple[bool, str | None, str | None]:
    """
    Check if the required adapter for a command is available.
    Returns (ok, adapter_id, adapter_status) tuple.
    """
    required_adapter, target = resolve_required_adapter(command)
    if not required_adapter:
        return True, None, None

    adapter_status = None
    if not isinstance(adapters, list):
        adapters = []

    for adapter in adapters:
        if adapter.get("id") == required_adapter:
            adapter_status = adapter.get("status")
            break

    if adapter_status != "ok":
        label = target or required_adapter
        error_msg = f"Hardware preflight failed: {label!r} needs adapter {required_adapter!r} but status is {adapter_status or 'missing'}"
        _emit_preflight_error(error_msg, yaml_output, quiet)
        return False, required_adapter, adapter_status

    return True, required_adapter, adapter_status


def _emit_preflight_error(error_msg: str, yaml_output: bool, quiet: bool) -> None:
    """Emit a preflight error in appropriate format."""
    if yaml_output:
        output_yaml({"status": "error", "message": error_msg}, quiet=quiet)
    else:
        click.echo(f"[ERROR] {error_msg}")


def emit_preflight_success(
    firmware_url: str,
    health: dict,
    identify: dict,
    required_adapter: str | None,
    adapter_status: str | None,
    yaml_output: bool,
    quiet: bool
) -> None:
    """Emit preflight success output in appropriate format."""
    if not quiet:
        if yaml_output:
            _emit_yaml_preflight(firmware_url, health, identify, required_adapter, adapter_status)
        else:
            _emit_text_preflight(firmware_url, health, identify, required_adapter, adapter_status)


def _emit_yaml_preflight(
    firmware_url: str,
    health: dict,
    identify: dict,
    required_adapter: str | None,
    adapter_status: str | None
) -> None:
    """Emit preflight success as YAML."""
    detected = int(identify.get("detected", 0) or 0)
    total = int(identify.get("total", 0) or 0)
    adapters = identify.get("adapters", [])
    if not isinstance(adapters, list):
        adapters = []

    preflight_data = {
        "status": "ok",
        "hardware_preflight": {
            "url": firmware_url,
            "mode": health.get("mode", "unknown"),
            "detected": f"{detected}/{total}",
            "adapters": adapters,
        },
    }
    if required_adapter:
        preflight_data["hardware_preflight"]["required"] = {
            "adapter": required_adapter,
            "status": adapter_status or "missing",
        }
    output_yaml(preflight_data, quiet=False)


def _emit_text_preflight(
    firmware_url: str,
    health: dict,
    identify: dict,
    required_adapter: str | None,
    adapter_status: str | None
) -> None:
    """Emit preflight success as human-readable text."""
    detected = int(identify.get("detected", 0) or 0)
    total = int(identify.get("total", 0) or 0)
    adapters = identify.get("adapters", [])
    if not isinstance(adapters, list):
        adapters = []

    click.echo("[PREFLIGHT] Hardware preflight")
    click.echo(f"  URL: {firmware_url}")
    click.echo(f"  Mode: {health.get('mode', 'unknown')}")
    click.echo(f"  Detected: {detected}/{total}")
    if required_adapter:
        click.echo(f"  Required: {required_adapter} ({adapter_status or 'missing'})")
    click.echo("  Adapters:")
    for adapter in adapters:
        click.echo(f"    - {adapter.get('id', 'unknown')}: {adapter.get('status', 'unknown')}")


def preflight_hardware(
    command: str,
    firmware_url: str,
    *,
    quiet: bool,
    yaml_output: bool = False
) -> bool:
    """
    Check whether the requested command can run on real hardware.

    Refactored from monolithic function (CC=28) to orchestrator pattern
    calling smaller focused functions (CC<10 each).
    """
    # Try to start firmware if not available
    if not ensure_firmware_running(firmware_url, quiet=quiet, yaml_output=yaml_output):
        return False

    # Check firmware state (health + identify)
    ok, health, identify = check_firmware_state(firmware_url, yaml_output, quiet)
    if not ok:
        return False

    # Check if required adapter is available
    adapters = identify.get("adapters", [])
    adapter_ok, required_adapter, adapter_status = check_required_adapter(
        command, adapters, yaml_output, quiet
    )
    if not adapter_ok:
        return False

    # Emit success output
    emit_preflight_success(
        firmware_url, health, identify,
        required_adapter, adapter_status,
        yaml_output, quiet
    )

    return True
