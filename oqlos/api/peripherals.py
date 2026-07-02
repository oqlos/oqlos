# firmware/api/peripherals.py
from typing import Any
from fastapi import APIRouter, HTTPException

from oqlos.models.peripheral import PeripheralMode
from oqlos.shared._endpoint_helpers import get_or_404, make_collection_route
from oqlos.api.utils import execution_ctrl as _ctrl

router = APIRouter(prefix="/api/v1/peripherals", tags=["peripherals"])

get_peripherals = make_collection_route(
    "get_peripherals",
    lambda: _ctrl.state_manager.peripherals,
)
router.get("")(get_peripherals)

@router.get("/{peripheral_id}")
async def get_peripheral(peripheral_id: str):
    """Get specific peripheral"""
    return get_or_404(_ctrl.state_manager.peripherals, peripheral_id, "Peripheral not found")

@router.put("/{peripheral_id}")
async def update_peripheral(peripheral_id: str, update_data: dict):
    """Update peripheral via PUT (for tests)"""
    if peripheral_id not in _ctrl.state_manager.peripherals:
        raise HTTPException(status_code=404, detail="Peripheral not found")
    
    peripheral = _ctrl.state_manager.peripherals[peripheral_id]
    
    if 'targetValue' in update_data:
        peripheral.targetValue = update_data['targetValue']
    if 'currentValue' in update_data:
        peripheral.currentValue = update_data['currentValue']
    if 'mode' in update_data:
        peripheral.mode = PeripheralMode(update_data['mode'])
    
    # Broadcast update
    await _ctrl.state_manager.broadcast_event({
        'type': 'peripheral_update',
        'peripheral': peripheral.model_dump()
    })
    
    return peripheral

@router.post("/{peripheral_id}/set")
async def set_peripheral(peripheral_id: str, value: Any, mode: str = 'manual'):
    """Update peripheral (manual mode)"""
    if peripheral_id not in _ctrl.state_manager.peripherals:
        raise HTTPException(status_code=404, detail="Peripheral not found")
    
    peripheral = _ctrl.state_manager.peripherals[peripheral_id]
    peripheral.mode = PeripheralMode(mode)
    peripheral.currentValue = value
    peripheral.targetValue = value
    
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
