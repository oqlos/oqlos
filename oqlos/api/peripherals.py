# firmware/api/peripherals.py
from typing import Any
from fastapi import APIRouter, HTTPException

from oqlos.models.peripheral import PeripheralMode
from oqlos.core.state import StateManager

router = APIRouter(prefix="/api/v1/peripherals", tags=["peripherals"])

# Will be set during app initialization
state_manager: StateManager = None

def set_state_manager(sm: StateManager):
    """Set the state manager instance"""
    global state_manager
    state_manager = sm

@router.get("")
async def get_peripherals():
    """Get all peripherals"""
    return list(state_manager.peripherals.values())

@router.get("/{peripheral_id}")
async def get_peripheral(peripheral_id: str):
    """Get specific peripheral"""
    if peripheral_id not in state_manager.peripherals:
        raise HTTPException(status_code=404, detail="Peripheral not found")
    return state_manager.peripherals[peripheral_id]

@router.put("/{peripheral_id}")
async def update_peripheral(peripheral_id: str, update_data: dict):
    """Update peripheral via PUT (for tests)"""
    if peripheral_id not in state_manager.peripherals:
        raise HTTPException(status_code=404, detail="Peripheral not found")
    
    peripheral = state_manager.peripherals[peripheral_id]
    
    if 'targetValue' in update_data:
        peripheral.targetValue = update_data['targetValue']
    if 'currentValue' in update_data:
        peripheral.currentValue = update_data['currentValue']
    if 'mode' in update_data:
        peripheral.mode = PeripheralMode(update_data['mode'])
    
    # Broadcast update
    await state_manager.broadcast_event({
        'type': 'peripheral_update',
        'peripheral': peripheral.model_dump()
    })
    
    return peripheral

@router.post("/{peripheral_id}/set")
async def set_peripheral(peripheral_id: str, value: Any, mode: str = 'manual'):
    """Update peripheral (manual mode)"""
    if peripheral_id not in state_manager.peripherals:
        raise HTTPException(status_code=404, detail="Peripheral not found")
    
    peripheral = state_manager.peripherals[peripheral_id]
    peripheral.mode = PeripheralMode(mode)
    peripheral.currentValue = value
    peripheral.targetValue = value
    
    # Broadcast update
    await state_manager.broadcast_event({
        'type': 'peripheral_update',
        'peripheral': peripheral.model_dump()
    })
    
    return peripheral

@router.post("/reset")
async def reset_peripherals():
    """Reset all peripherals"""
    state_manager.initialize_peripherals()
    return {"status": "reset"}
