"""Validated Linux network identity changes with reconnect verification and rollback."""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import subprocess
from dataclasses import dataclass
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NETWORK_IDENTITY_VERSION = "network-identity-v1"
_HOSTNAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class NetworkIdentityError(RuntimeError):
    pass


class NetworkIdentityConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["network-identity-v1"] = Field(
        default=NETWORK_IDENTITY_VERSION, alias="schemaVersion"
    )
    node_id: Literal["displaynet", "boardnet", "maskfleet"]
    hostname: str
    connection: str = Field(min_length=1, max_length=128)
    ipv4_mode: Literal["dhcp", "static"] = "dhcp"
    ipv4_address: str = ""
    ipv4_prefix: int = Field(default=24, ge=1, le=32)
    ipv4_gateway: str = ""
    ipv4_dns: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_identity(self) -> "NetworkIdentityConfiguration":
        self.hostname = self.hostname.strip().lower().removesuffix(".local")
        if not _HOSTNAME.fullmatch(self.hostname):
            raise ValueError("hostname must be one RFC 1123 label")
        if self.ipv4_mode == "static":
            if not self.ipv4_address or not self.ipv4_gateway:
                raise ValueError("static mode requires ipv4_address and ipv4_gateway")
            ipaddress.IPv4Address(self.ipv4_address)
            ipaddress.IPv4Address(self.ipv4_gateway)
        for value in self.ipv4_dns:
            ipaddress.IPv4Address(value)
        return self


def build_apply_commands(config: NetworkIdentityConfiguration) -> list[list[str]]:
    commands = [["hostnamectl", "set-hostname", config.hostname]]
    if config.ipv4_mode == "dhcp":
        commands.append(["nmcli", "connection", "modify", config.connection,
                         "ipv4.method", "auto", "ipv4.addresses", "",
                         "ipv4.gateway", "", "ipv4.dns", ""])
    else:
        commands.append(["nmcli", "connection", "modify", config.connection,
                         "ipv4.method", "manual",
                         "ipv4.addresses", f"{config.ipv4_address}/{config.ipv4_prefix}",
                         "ipv4.gateway", config.ipv4_gateway,
                         "ipv4.dns", ",".join(config.ipv4_dns)])
    commands.append(["nmcli", "connection", "up", config.connection])
    return commands


def apply_network_identity(
    config: NetworkIdentityConfiguration,
    *,
    dry_run: bool = True,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, object]:
    commands = build_apply_commands(config)
    if dry_run:
        return {"ok": True, "contract": NETWORK_IDENTITY_VERSION, "dry_run": True,
                "configuration": config.model_dump(by_alias=True), "commands": commands}
    if os.getenv("OQLOS_ALLOW_NETWORK_IDENTITY", "").lower() not in {"1", "true", "yes"}:
        raise NetworkIdentityError("network identity apply is disabled by local policy")

    previous_hostname = socket.gethostname()
    snapshot = runner(
        ["nmcli", "--show-secrets", "connection", "export", config.connection],
        check=True, capture_output=True, text=True,
    ).stdout
    try:
        for command in commands:
            runner(command, check=True, capture_output=True, text=True, timeout=30)
        probe = runner(["nmcli", "-g", "GENERAL.STATE", "connection", "show", config.connection],
                       check=True, capture_output=True, text=True, timeout=15).stdout.strip()
        if not probe.startswith("activated"):
            raise NetworkIdentityError(f"connection verification failed: {probe}")
    except Exception as exc:
        runner(["hostnamectl", "set-hostname", previous_hostname], check=False,
               capture_output=True, text=True)
        runner(["nmcli", "connection", "load", "/dev/stdin"], input=snapshot, check=False,
               capture_output=True, text=True)
        runner(["nmcli", "connection", "up", config.connection], check=False,
               capture_output=True, text=True)
        raise NetworkIdentityError(f"apply failed and rollback was attempted: {exc}") from exc
    return {"ok": True, "contract": NETWORK_IDENTITY_VERSION, "dry_run": False,
            "hostname": config.hostname, "connection": config.connection,
            "reconnect_verified": True}
