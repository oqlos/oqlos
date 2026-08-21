from __future__ import annotations

from oqlos.hardware.plugins._m5_core_http import CoreS3HttpClient


class _Capabilities:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def token(self, capability: str, resource: str) -> str:
        self.calls.append((capability, resource))
        return "short-lived-token"


def test_stacknet_scope_is_exact_for_coil_and_safety_operations() -> None:
    assert CoreS3HttpClient._authorization_scope("lease_acquire", {}) == (
        "hardware.node.output.set", "hardware-node:stacknet/output/lease"
    )
    assert CoreS3HttpClient._authorization_scope("set_coil", {"coil": 7}) == (
        "hardware.node.output.set", "hardware-node:stacknet/output/8"
    )
    assert CoreS3HttpClient._authorization_scope("all_outputs_off", {}) == (
        "hardware.node.outputs.all-off", "hardware-node:stacknet/outputs"
    )
