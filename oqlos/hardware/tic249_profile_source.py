"""Validate, apply and persist the BoardNet Tic249 device OQL profile."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx

from oqlos.hardware.client.tic249_sidecar_client import tic249_sidecar_base_urls
from oqlos.hardware.sidecar_control import _run_cmd, ensure_tic249_sidecar

TIC249_CONTINUOUS_SAFE_MAX_MA = 1_800
_MAX_SOURCE_BYTES = 256 * 1024
_PREFIX = "device.boardnet.motor-tic249."
_VERSION_RE = re.compile(r"^\s*VERSION\s*:\s*6\s*$", re.IGNORECASE | re.MULTILINE)
_SET_RE = re.compile(
    r"""^\s*SET\s+['\"]([^'\"]+)['\"]\s+['\"]([^'\"]*)['\"]\s*$""",
    re.IGNORECASE | re.MULTILINE,
)


class Tic249ProfileSourceError(ValueError):
    """The proposed device profile is incomplete, invalid, or unsafe."""


class Tic249ProfileUnsafeError(RuntimeError):
    """The profile cannot be changed while the motor is active."""


class Tic249ProfileUnavailableError(RuntimeError):
    """The sidecar or host provisioning path is unavailable."""


def _parse_bool(raw: str, field: str) -> bool:
    token = str(raw).strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    raise Tic249ProfileSourceError(f"{field} must be true or false")


def _current_ma_to_code(current_ma: int) -> int:
    if current_ma < 0 or current_ma > TIC249_CONTINUOUS_SAFE_MAX_MA:
        raise Tic249ProfileSourceError(
            "current_limit_ma must be between 0 and "
            f"{TIC249_CONTINUOUS_SAFE_MAX_MA} mA"
        )
    if current_ma % 40:
        raise Tic249ProfileSourceError("current_limit_ma must be a multiple of 40 mA")
    code = current_ma // 40
    achievable = (
        0 <= code <= 31
        or 32 <= code <= 62 and code % 2 == 0
        or 64 <= code <= 124 and code % 4 == 0
    )
    if not achievable:
        raise Tic249ProfileSourceError(
            f"Tic249 cannot represent {current_ma} mA exactly; "
            "choose an achievable value such as 1600 or 1760 mA"
        )
    return code


def _build_nvm_profile(
    *, forward_pin: str, reverse_pin: str, pull_up: bool, active_high: bool
) -> dict[str, Any]:
    pins: dict[str, dict[str, bool]] = {}
    settings_file: dict[str, str] = {}
    for pin in ("scl", "sda"):
        direction = "forward" if pin == forward_pin else "reverse"
        pins[pin] = {
            "limit_switch_forward": direction == "forward",
            "limit_switch_reverse": direction == "reverse",
            "enable_pull_up": pull_up,
            "active_high": active_high,
        }
        tokens = []
        if pull_up:
            tokens.append("pullup")
        if active_high:
            tokens.append("active_high")
        tokens.append(f"limit_switch_{direction}")
        settings_file[f"{pin}_config"] = " ".join(tokens)
    return {
        "profile_id": "boardnet-tic249-oql-v1",
        "description": (
            f"BoardNet OQL: {forward_pin.upper()}=limit forward, "
            f"{reverse_pin.upper()}=limit reverse"
        ),
        "product": "T249",
        "pins": pins,
        "settings_file": settings_file,
    }


def validate_tic249_profile_source(content: str) -> dict[str, Any]:
    source = str(content or "")
    if not source.strip():
        raise Tic249ProfileSourceError("Tic249 profile source must not be empty")
    if len(source.encode("utf-8")) > _MAX_SOURCE_BYTES:
        raise Tic249ProfileSourceError("Tic249 profile source is too large")
    if not _VERSION_RE.search(source):
        raise Tic249ProfileSourceError("Tic249 profile must declare VERSION: 6")

    values = {
        key[len(_PREFIX) :]: value.strip()
        for key, value in _SET_RE.findall(source)
        if key.startswith(_PREFIX)
    }
    required = (
        "current_limit_ma",
        "limit_switch_forward_pin",
        "limit_switch_reverse_pin",
        "limit_switch_pull_up",
        "limit_switch_active_high",
    )
    missing = [field for field in required if field not in values]
    if missing:
        raise Tic249ProfileSourceError(
            f"Missing Tic249 OQL setting(s): {', '.join(missing)}"
        )

    try:
        current_limit_ma = int(values["current_limit_ma"])
    except ValueError as exc:
        raise Tic249ProfileSourceError("current_limit_ma must be an integer") from exc
    current_limit_code = _current_ma_to_code(current_limit_ma)
    forward_pin = values["limit_switch_forward_pin"].lower()
    reverse_pin = values["limit_switch_reverse_pin"].lower()
    if forward_pin not in {"scl", "sda"} or reverse_pin not in {"scl", "sda"}:
        raise Tic249ProfileSourceError("limit-switch pins must be scl or sda")
    if forward_pin == reverse_pin:
        raise Tic249ProfileSourceError(
            "forward and reverse limit switches must use different pins"
        )
    pull_up = _parse_bool(values["limit_switch_pull_up"], "limit_switch_pull_up")
    active_high = _parse_bool(
        values["limit_switch_active_high"], "limit_switch_active_high"
    )
    return {
        "current_limit_ma": current_limit_ma,
        "current_limit_code": current_limit_code,
        "current_measurement_available": False,
        "limit_switch_forward_pin": forward_pin,
        "limit_switch_reverse_pin": reverse_pin,
        "limit_switch_pull_up": pull_up,
        "limit_switch_active_high": active_high,
        "nvm_profile": _build_nvm_profile(
            forward_pin=forward_pin,
            reverse_pin=reverse_pin,
            pull_up=pull_up,
            active_high=active_high,
        ),
    }


def _scenario_target() -> Path:
    explicit = os.getenv("OQLOS_TIC249_DEVICE_OQL", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    root = os.getenv("OQLOS_SCENARIOS_DIR", "").strip()
    if root:
        return Path(root).expanduser() / "layers/hardware/devices/tic249-boardnet.oql"
    relative = Path("layers/hardware/devices/tic249-boardnet.oql")
    here = Path(__file__).resolve()
    candidates = (
        here.parents[3] / "oql-scenario" / relative,
        Path.home() / "maskservice/oql-scenario" / relative,
        Path.home() / "oqlos/oql-scenario" / relative,
    )
    return next((path for path in candidates if path.is_file()), candidates[0])


def _nvm_profile_target() -> Path:
    explicit = os.getenv("OQLOS_TIC249_NVM_PROFILE", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    return Path.home() / "maskservice/rpi-motor-tic249/config/boardnet_nvm_profile.json"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(raw_temp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            os.chmod(temp_path, path.stat().st_mode & 0o777)
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


async def _sidecar_request(
    method: str, path: str, *, payload: dict[str, Any] | None = None
) -> tuple[dict[str, Any], str]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
        for base in tic249_sidecar_base_urls():
            try:
                response = await client.request(method, f"{base}{path}", json=payload)
            except (httpx.HTTPError, OSError):
                continue
            body = response.json() if response.content else {}
            if response.status_code < 300 and isinstance(body, dict):
                return body, base
    raise Tic249ProfileUnavailableError("Tic249 sidecar is unavailable")


def _assert_motor_safe(status: dict[str, Any]) -> None:
    velocity = int(status.get("velocity") or 0)
    active = bool(status.get("reciprocating_active") or status.get("homing_active"))
    if velocity != 0 or active or status.get("energized") is not False:
        raise Tic249ProfileUnsafeError(
            "Stop AL and wait until velocity=0 and energized=false before saving "
            "the Tic249 pin/current profile"
        )


async def _nvm_matches_desired(desired: dict[str, Any]) -> bool:
    target = _nvm_profile_target()
    try:
        stored = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if stored != desired:
        return False
    try:
        validation, _base = await _sidecar_request("GET", "/api/nvm-validation")
    except Tic249ProfileUnavailableError:
        return False
    return validation.get("ok") is True


async def _apply_nvm_profile(profile: dict[str, Any]) -> dict[str, Any]:
    if not shutil.which("systemctl"):
        raise Tic249ProfileUnavailableError("systemctl is unavailable on BoardNet")
    target = _nvm_profile_target()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(prefix="tic249-oql-", suffix=".json", dir=target.parent)
    os.close(fd)
    temp_path = Path(raw_temp)
    temp_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    root = target.parent.parent
    python = Path(
        os.getenv("OQLOS_TIC249_PYTHON", str(root / ".venv/bin/python"))
    ).expanduser()
    provision = Path(
        os.getenv("OQLOS_TIC249_PROVISION_CLI", str(root / "provision_cli.py"))
    ).expanduser()
    if not python.is_file():
        python = Path(sys.executable)
    if not provision.is_file():
        temp_path.unlink(missing_ok=True)
        raise Tic249ProfileUnavailableError(f"Tic249 provision CLI not found: {provision}")

    stopped = False
    try:
        rc, _out, err = await _run_cmd(
            "systemctl", "--user", "stop", "hw-tic249.service", timeout=15.0
        )
        stopped = rc == 0
        if rc != 0:
            raise Tic249ProfileUnavailableError(
                f"Could not stop hw-tic249.service: {err.strip()}"
            )
        rc, out, err = await _run_cmd(
            str(python),
            str(provision),
            "--profile",
            str(temp_path),
            "apply",
            "--yes",
            timeout=45.0,
        )
        if rc != 0:
            raise Tic249ProfileUnavailableError(
                f"Tic249 NVM provisioning failed: {(err or out).strip()}"
            )
        result = json.loads(out) if out.strip() else {"ok": True}
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise Tic249ProfileUnavailableError("Tic249 NVM verification failed")
        _atomic_write(target, json.dumps(profile, indent=2) + "\n")
    finally:
        temp_path.unlink(missing_ok=True)
        if stopped:
            await _run_cmd(
                "systemctl", "--user", "start", "hw-tic249.service", timeout=15.0
            )
    ready = await ensure_tic249_sidecar()
    if not ready.get("ok"):
        raise Tic249ProfileUnavailableError(
            str(ready.get("error") or "Tic249 sidecar did not restart")
        )
    return result


async def apply_tic249_profile_source(content: str) -> dict[str, Any]:
    """Apply a deenergized profile, then atomically persist its OQL source."""
    configured = validate_tic249_profile_source(content)
    status, base = await _sidecar_request("GET", "/api/status")
    _assert_motor_safe(status)

    nvm_applied = False
    nvm_result: dict[str, Any] = {"ok": True, "changed": False}
    if not await _nvm_matches_desired(configured["nvm_profile"]):
        nvm_result = await _apply_nvm_profile(configured["nvm_profile"])
        nvm_applied = True

    current_result, base = await _sidecar_request(
        "POST",
        "/api/config",
        payload={"motor": {"current_limit_ma": configured["current_limit_ma"]}},
    )
    source_target = _scenario_target()
    normalized = content if content.endswith("\n") else f"{content}\n"
    _atomic_write(source_target, normalized)
    return {
        "path": str(source_target),
        "sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "configured": {
            key: value for key, value in configured.items() if key != "nvm_profile"
        },
        "effective": current_result.get("motor", current_result),
        "nvm": {**nvm_result, "applied": nvm_applied},
        "sidecar_base_url": base,
    }


__all__ = [
    "TIC249_CONTINUOUS_SAFE_MAX_MA",
    "Tic249ProfileSourceError",
    "Tic249ProfileUnavailableError",
    "Tic249ProfileUnsafeError",
    "apply_tic249_profile_source",
    "validate_tic249_profile_source",
]
