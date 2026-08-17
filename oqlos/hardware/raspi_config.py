"""Declarative Raspberry Pi raspi-config (OQL/YAML/JSON).

Desired host settings are stored as ``raspi.config.*`` SET keys and applied
only through a fixed ``raspi-config nonint`` allowlist. Secrets (Wi-Fi PSK,
passwords) are rejected. Apply is dry-run unless policy allows it.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from oqlos.core.oql_versioning import OQL_VERSION_CURRENT

RASPI_CONFIG_VERSION = "raspi-config-v1"
SUPPORTED_RASPI_CONFIG_FORMATS = ("oql", "yaml", "json")
_OQL_KEY_PREFIX = "raspi.config."
_WIFI_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_SECRET_KEY = re.compile(r"(?:ssid|psk|passphrase|password|passwd|token|secret)", re.I)

# raspi-config nonint: 0 = enable, 1 = disable
INTERFACE_COMMANDS: dict[str, tuple[str, str]] = {
    "i2c": ("get_i2c", "do_i2c"),
    "spi": ("get_spi", "do_spi"),
    "serial_hw": ("get_serial_hw", "do_serial_hw"),
    "serial_cons": ("get_serial_cons", "do_serial_cons"),
    "ssh": ("get_ssh", "do_ssh"),
    "vnc": ("get_vnc", "do_vnc"),
    "onewire": ("get_onewire", "do_onewire"),
    "camera": ("get_camera", "do_camera"),
}


class RaspiConfigError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        format: str | None = None,
        source: str | None = None,
        issues: list[dict[str, Any]] | None = None,
    ) -> None:
        self.format = format
        self.source = source
        self.issues = issues or []
        context = ", ".join(part for part in (format, source) if part)
        super().__init__(f"{message}{f' ({context})' if context else ''}")


class RaspiInterfaces(BaseModel):
    model_config = ConfigDict(extra="forbid")

    i2c: bool | None = None
    spi: bool | None = None
    serial_hw: bool | None = None
    serial_cons: bool | None = None
    ssh: bool | None = None
    vnc: bool | None = None
    onewire: bool | None = None
    camera: bool | None = None


class RaspiConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["raspi-config-v1"] = Field(
        default=RASPI_CONFIG_VERSION, alias="schemaVersion"
    )
    interfaces: RaspiInterfaces = Field(default_factory=RaspiInterfaces)
    wifi_country: str | None = Field(default=None, alias="wifiCountry")

    @field_validator("wifi_country")
    @classmethod
    def _country(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        code = str(value).strip().upper()
        if not _WIFI_COUNTRY_RE.fullmatch(code):
            raise ValueError("wifiCountry must be an ISO 3166-1 alpha-2 code")
        return code

    @model_validator(mode="before")
    @classmethod
    def _reject_secrets(cls, value: Any) -> Any:
        if isinstance(value, dict):
            for key in value:
                if _SECRET_KEY.search(str(key)) and str(key) not in {"wifiCountry"}:
                    raise ValueError(
                        f"raspi-config rejects secret field {key!r}; use NetworkManager separately"
                    )
        return value

    def canonical_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schemaVersion": self.schema_version,
            "interfaces": {
                key: value
                for key, value in self.interfaces.model_dump().items()
                if value is not None
            },
        }
        if self.wifi_country:
            payload["wifiCountry"] = self.wifi_country
        return payload

    def desired_interfaces(self) -> dict[str, bool]:
        return {
            key: value
            for key, value in self.interfaces.model_dump().items()
            if value is not None
        }


def parse_raspi_configuration(
    content: str,
    format: str,
    *,
    source: str | None = None,
) -> RaspiConfiguration:
    mode = str(format or "").strip().lower()
    try:
        if mode == "json":
            value = json.loads(content)
        elif mode == "yaml":
            value = yaml.safe_load(content)
        elif mode == "oql":
            value = _parse_oql(content, source)
        else:
            raise RaspiConfigError(
                "unsupported format; expected oql, yaml, or json", format=mode, source=source
            )
    except RaspiConfigError:
        raise
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise RaspiConfigError(str(exc), format=mode, source=source) from exc
    try:
        return RaspiConfiguration.model_validate(value)
    except ValidationError as exc:
        issues = [
            {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
            for error in exc.errors()
        ]
        detail = issues[0]["message"] if issues else "invalid value"
        raise RaspiConfigError(
            f"raspi-config validation failed: {detail}",
            format=mode,
            source=source,
            issues=issues,
        ) from exc


def serialize_raspi_configuration(config: RaspiConfiguration, format: str) -> str:
    mode = str(format or "").strip().lower()
    data = config.canonical_dict()
    if mode == "json":
        return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if mode == "yaml":
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=True)
    if mode == "oql":
        return _dump_oql(config)
    raise RaspiConfigError("unsupported format; expected oql, yaml, or json", format=mode)


def _parse_oql(text: str, source: str | None) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped.upper().startswith("SET "):
            continue
        try:
            tokens = shlex.split(stripped, comments=True, posix=True)
        except ValueError as exc:
            raise RaspiConfigError(
                f"invalid OQL SET at line {line_number}: {exc}", format="oql", source=source
            ) from exc
        if len(tokens) != 3 or tokens[0].upper() != "SET" or not tokens[1].startswith(_OQL_KEY_PREFIX):
            continue
        field = tokens[1][len(_OQL_KEY_PREFIX) :]
        try:
            document[field] = json.loads(tokens[2])
        except json.JSONDecodeError as exc:
            raise RaspiConfigError(
                f"invalid JSON value for {field} at line {line_number}: {exc.msg}",
                format="oql",
                source=source,
            ) from exc
    if not document:
        raise RaspiConfigError(
            f"no {_OQL_KEY_PREFIX}* SET declarations found", format="oql", source=source
        )
    return document


def _dump_oql(config: RaspiConfiguration) -> str:
    lines = [
        f"VERSION: {OQL_VERSION_CURRENT}",
        "SCENARIO: Raspberry Pi raspi-config",
        "CATEGORY: raspi-config",
        "DESCRIPTION: Declarative raspi-config nonint settings; generated deterministically.",
        "",
        "CONFIG:",
        "  NAME 'Raspberry Pi raspi-config'",
    ]
    for field, value in config.canonical_dict().items():
        compact = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        quoted = json.dumps(compact, ensure_ascii=False)
        lines.append(f"  SET '{_OQL_KEY_PREFIX}{field}' {quoted}")
    return "\n".join(lines) + "\n"


def _run_raspi(args: list[str], *, runner: Any | None = None) -> subprocess.CompletedProcess[str]:
    if runner is not None:
        return runner(args)
    binary = shutil.which("raspi-config")
    if not binary:
        raise RaspiConfigError("raspi-config is not installed")
    command = [binary, "nonint", *args]
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        sudo = shutil.which("sudo")
        if not sudo:
            raise RaspiConfigError("raspi-config requires root or passwordless sudo")
        command = [sudo, "-n", *command]
    return subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=20,
        env={**os.environ, "LC_ALL": "C"},
    )


def _enabled_from_get(stdout: str, returncode: int) -> bool | None:
    token = stdout.strip().splitlines()[-1].strip() if stdout.strip() else ""
    if token in {"0", "enabled", "on", "true"}:
        return True
    if token in {"1", "disabled", "off", "false"}:
        return False
    if returncode == 0 and token == "":
        return None
    return None


def probe_raspi_config(*, runner: Any | None = None) -> dict[str, Any]:
    if shutil.which("raspi-config") is None:
        return {
            "supported": False,
            "control_allowed": os.environ.get("OQLOS_ALLOW_RASPI_CONFIG", "0") == "1",
            "interfaces": {},
            "wifiCountry": None,
            "error": "raspi-config is not installed",
        }
    interfaces: dict[str, bool | None] = {}
    errors: list[str] = []
    for name, (getter, _setter) in INTERFACE_COMMANDS.items():
        try:
            completed = _run_raspi([getter], runner=runner)
        except RaspiConfigError as exc:
            errors.append(str(exc))
            interfaces[name] = None
            continue
        interfaces[name] = _enabled_from_get(completed.stdout, completed.returncode)
        if completed.returncode != 0 and interfaces[name] is None:
            errors.append(f"{getter} exit {completed.returncode}")
    wifi_country = None
    try:
        country = _run_raspi(["get_wifi_country"], runner=runner)
        token = country.stdout.strip().splitlines()[-1].strip() if country.stdout.strip() else ""
        if _WIFI_COUNTRY_RE.fullmatch(token.upper()):
            wifi_country = token.upper()
    except RaspiConfigError as exc:
        errors.append(str(exc))
    return {
        "supported": True,
        "control_allowed": os.environ.get("OQLOS_ALLOW_RASPI_CONFIG", "0") == "1",
        "interfaces": interfaces,
        "wifiCountry": wifi_country,
        "error": "; ".join(errors) if errors else None,
    }


def plan_raspi_config(
    desired: RaspiConfiguration,
    current: dict[str, Any] | None = None,
    *,
    runner: Any | None = None,
) -> list[dict[str, Any]]:
    observed = current or probe_raspi_config(runner=runner)
    steps: list[dict[str, Any]] = []
    observed_interfaces = observed.get("interfaces") or {}
    for name, enabled in desired.desired_interfaces().items():
        getter, setter = INTERFACE_COMMANDS[name]
        actual = observed_interfaces.get(name)
        steps.append(
            {
                "key": f"interfaces.{name}",
                "command": setter,
                "argv": [setter, "0" if enabled else "1"],
                "desired": enabled,
                "current": actual,
                "changed": actual is not True if enabled else actual is not False,
                "probe": getter,
            }
        )
    if desired.wifi_country:
        actual_country = observed.get("wifiCountry")
        steps.append(
            {
                "key": "wifiCountry",
                "command": "do_wifi_country",
                "argv": ["do_wifi_country", desired.wifi_country],
                "desired": desired.wifi_country,
                "current": actual_country,
                "changed": actual_country != desired.wifi_country,
                "probe": "get_wifi_country",
            }
        )
    return steps


def apply_raspi_config(
    desired: RaspiConfiguration,
    *,
    dry_run: bool = True,
    runner: Any | None = None,
) -> dict[str, Any]:
    allowed = os.environ.get("OQLOS_ALLOW_RASPI_CONFIG", "0") == "1"
    current = probe_raspi_config(runner=runner)
    steps = plan_raspi_config(desired, current, runner=runner)
    if not dry_run and not allowed:
        raise RaspiConfigError("raspi-config apply is disabled by local policy (OQLOS_ALLOW_RASPI_CONFIG)")
    if not dry_run and not current.get("supported"):
        raise RaspiConfigError(current.get("error") or "raspi-config is not available")
    applied: list[dict[str, Any]] = []
    for step in steps:
        record = dict(step)
        if dry_run or not step["changed"]:
            record["applied"] = False
            applied.append(record)
            continue
        completed = _run_raspi(list(step["argv"]), runner=runner)
        if completed.returncode != 0:
            detail = (completed.stdout or "").strip()[-400:] or f"exit {completed.returncode}"
            raise RaspiConfigError(f"cannot apply {step['command']}: {detail}")
        record["applied"] = True
        applied.append(record)
    return {
        "ok": True,
        "dry_run": dry_run,
        "contract": RASPI_CONFIG_VERSION,
        "desired": desired.canonical_dict(),
        "current": current,
        "steps": applied,
    }
