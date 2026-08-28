import subprocess

import pytest

from oqlos.hardware.network_identity import (
    NetworkIdentityConfiguration,
    NetworkIdentityError,
    apply_network_identity,
    build_apply_commands,
)


def configuration(**overrides):
    values = {"node_id": "boardnet", "hostname": "boardnet.local", "connection": "lan0"}
    values.update(overrides)
    return NetworkIdentityConfiguration(**values)


def test_dhcp_plan_normalizes_mdns_hostname():
    config = configuration()
    assert config.hostname == "boardnet"
    assert build_apply_commands(config)[1][-6:] == ["ipv4.method", "auto", "ipv4.addresses", "", "ipv4.gateway", "", "ipv4.dns", ""][-6:]


def test_static_requires_address_and_gateway():
    with pytest.raises(ValueError):
        configuration(ipv4_mode="static")


def test_dry_run_never_executes_commands():
    def forbidden(*args, **kwargs):
        raise AssertionError("runner called")
    result = apply_network_identity(configuration(), runner=forbidden)
    assert result["dry_run"] is True
    assert result["configuration"]["hostname"] == "boardnet"


def test_live_apply_is_policy_guarded(monkeypatch):
    monkeypatch.delenv("OQLOS_ALLOW_NETWORK_IDENTITY", raising=False)
    with pytest.raises(NetworkIdentityError, match="disabled"):
        apply_network_identity(configuration(), dry_run=False)
