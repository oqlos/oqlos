# firmware/api/peripherals.py
from typing import Any
from fastapi import APIRouter

from oqlos.errors import OqlosError
from oqlos.models.peripheral import PeripheralMode
from oqlos.core.cqrs.peripheral import SetPeripheralModeCommand, SetPeripheralValueCommand
from oqlos.shared._endpoint_helpers import make_collection_route
from oqlos.api.utils import execution_ctrl as _ctrl

router = APIRouter(prefix="/api/v1/peripherals", tags=["peripherals"])

get_peripherals = make_collection_route(
    "get_peripherals",
    lambda: _ctrl.state_manager.peripherals,
)
router.get("")(get_peripherals)


def _get_peripheral_or_error(peripheral_id: str, *, operation_id: str):
    peripheral = _ctrl.state_manager.peripherals.get(peripheral_id)
    if peripheral is None:
        raise OqlosError(
            code="api_peripheral_not_found",
            status_code=404,
            detail={
                "architecture": "SOA",
                "layer": "firmware",
                "component": "peripheral-registry",
                "stage": "peripheral.lookup",
                "problem_source": "request",
                "operation_id": operation_id,
            },
        )
    return peripheral

@router.get("/{peripheral_id}")
async def get_peripheral(peripheral_id: str):
    """Get specific peripheral"""
    return _get_peripheral_or_error(peripheral_id, operation_id="peripheral.get")

@router.put("/{peripheral_id}")
async def update_peripheral(peripheral_id: str, update_data: dict):
    """Update peripheral via PUT (for tests)"""
    peripheral = _get_peripheral_or_error(
        peripheral_id, operation_id="peripheral.update"
    )
    bus = _ctrl.state_manager.command_bus

    if 'targetValue' in update_data or 'currentValue' in update_data:
        bus.dispatch(SetPeripheralValueCommand(
            peripheral_id=peripheral_id,
            current_value=update_data.get('currentValue', peripheral.currentValue),
            target_value=update_data.get('targetValue', peripheral.targetValue),
        ))
    if 'mode' in update_data:
        bus.dispatch(SetPeripheralModeCommand(
            peripheral_id=peripheral_id,
            mode=PeripheralMode(update_data['mode']),
        ))

    peripheral = _ctrl.state_manager.peripherals[peripheral_id]
    # Broadcast update
    await _ctrl.state_manager.broadcast_event({
        'type': 'peripheral_update',
        'peripheral': peripheral.model_dump()
    })

    return peripheral

@router.post("/{peripheral_id}/set")
async def set_peripheral(peripheral_id: str, value: Any, mode: str = 'manual'):
    """Update peripheral (manual mode)"""
    _get_peripheral_or_error(peripheral_id, operation_id="peripheral.set")

    bus = _ctrl.state_manager.command_bus
    bus.dispatch(SetPeripheralModeCommand(peripheral_id=peripheral_id, mode=PeripheralMode(mode)))
    bus.dispatch(SetPeripheralValueCommand(peripheral_id=peripheral_id, current_value=value, target_value=value))

    peripheral = _ctrl.state_manager.peripherals[peripheral_id]
    # Broadcast update
    await _ctrl.state_manager.broadcast_event({
        'type': 'peripheral_update',
        'peripheral': peripheral.model_dump()
    })

    return peripheral

@router.post("/reset")
async def reset_peripherals():
    """Reset all peripherals"""
    _ctrl.state_manager.initialize_peripherals()
    return {"status": "reset"}
