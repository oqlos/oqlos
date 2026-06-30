"""OqlOS API client configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from oqlos.hardware.client.constants import DEFAULT_OQLOS_API_BASE


def float_from_env(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def int_from_env(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def candidate_oqlos_bases(api_base: str) -> list[str]:
    configured = (api_base or DEFAULT_OQLOS_API_BASE).rstrip("/")
    candidates = [configured]
    if configured.endswith(":8202"):
        candidates.append(configured[:-5] + ":8200")
    elif configured.endswith(":8200"):
        candidates.append(configured[:-5] + ":8202")
    deduped: list[str] = []
    for item in candidates:
        if item not in deduped:
            deduped.append(item)
    return deduped


@dataclass(frozen=True)
class OqlosHardwareProxyConfig:
    api_base: str = DEFAULT_OQLOS_API_BASE
    timeout_seconds: float = 45.0
    identify_timeout_seconds: float | None = None
    connect_timeout_seconds: float = 2.0
    proxy_prefix: str = "/api/v3/hardware"
    api_base_source: str = "default"
    runtime_name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "api_base", (self.api_base or DEFAULT_OQLOS_API_BASE).rstrip("/"))
        if self.identify_timeout_seconds is None:
            object.__setattr__(self, "identify_timeout_seconds", self.timeout_seconds)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        proxy_prefix: str = "/api/v3/hardware",
    ) -> OqlosHardwareProxyConfig:
        values = env or os.environ
        timeout = float_from_env(values, "OQLOS_API_TIMEOUT_SECONDS", 45.0)
        # Precedence: the canonical hardware-runtime URL (set when pointing at a
        # dedicated/remote hardware node) wins over the generic OQLOS_API_URL.
        runtime_url = values.get("C2004_HARDWARE_RUNTIME_URL")
        oqlos_url = values.get("OQLOS_API_URL")
        if runtime_url:
            api_base, source = runtime_url, "C2004_HARDWARE_RUNTIME_URL"
        elif oqlos_url:
            api_base, source = oqlos_url, "OQLOS_API_URL"
        else:
            api_base, source = DEFAULT_OQLOS_API_BASE, "default"
        return cls(
            api_base=api_base,
            timeout_seconds=timeout,
            identify_timeout_seconds=float_from_env(values, "OQLOS_API_IDENTIFY_TIMEOUT_SECONDS", timeout),
            connect_timeout_seconds=float_from_env(values, "OQLOS_CONNECT_TIMEOUT_SECONDS", 2.0),
            proxy_prefix=proxy_prefix,
            api_base_source=source,
            runtime_name=values.get("C2004_HARDWARE_RUNTIME_NAME") or None,
        )
