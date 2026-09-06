"""Recovery failure contracts are tested with mocked transports only."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from oqlos.hardware import diagnosis
from oqlos.hardware.plugins.modbus import ModbusPlugin
from oqlos.hardware.plugins.base import PluginConfig


@pytest.mark.asyncio
async def test_register_failure_has_code_and_original_error():
    plugin = ModbusPlugin(PluginConfig(plugin_id="modbus-io", connection_type="modbus-rtu"))
    plugin._rtu_call = AsyncMock(return_value=None)
    result = await plugin._execute_write_holding_register({"address": 0, "value": 1})
    assert result["success"] is False
    assert result["error"] == "None"
    assert result["error_code"] == "C2004-HW-0012"


@pytest.mark.asyncio
@pytest.mark.parametrize("raises", [False, True])
async def test_failed_safe_stop_never_confirms_recovery(monkeypatch, raises):
    gateway = SimpleNamespace(health=AsyncMock(return_value={}),
        apply_modbus_user_settings=AsyncMock(return_value={"reconnects": []}))
    if raises:
        gateway.all_valves_off = AsyncMock(side_effect=RuntimeError("stop failed"))
    monkeypatch.setattr(diagnosis, "_recover_targets", lambda *a, **kw: ["modbus-io"])
    monkeypatch.setattr(diagnosis, "_repair_sidecar_if_needed", AsyncMock())
    monkeypatch.setattr(diagnosis, "_still_failed_plugins", lambda *a: [])
    monkeypatch.setattr(diagnosis, "_host_actions_from_report", lambda *a, **kw: [])
    result = await diagnosis.execute_safe_recover(gateway, SimpleNamespace(),
        plugin_ids=("modbus-io", "io-m5-4in8out"))
    assert result["ok"] is False
    assert result["safe_state"]["confirmed"] is False
    assert result["safe_state"]["after"]["error_code"] == "C2004-HW-0012"
