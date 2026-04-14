# firmware/models/peripherals.py
from enum import Enum
from typing import Any
from pydantic import BaseModel

class PeripheralType(str, Enum):
    PRESSURE_SENSOR = 'pressure_sensor'
    VALVE = 'valve'
    PUMP = 'pump'
    ARTIFICIAL_LUNG = 'artificial_lung'
    ENCODER = 'encoder'
    BUTTON = 'button'

class PeripheralStatus(str, Enum):
    OK = 'ok'
    WARNING = 'warning'
    ERROR = 'error'

class PeripheralMode(str, Enum):
    AUTO = 'auto'
    MANUAL = 'manual'

class Peripheral(BaseModel):
    id: str
    type: PeripheralType
    name: str
    currentValue: Any
    targetValue: Any
    unit: str | None = None
    range: dict[str, float] | None = None
    status: PeripheralStatus = PeripheralStatus.OK
    mode: PeripheralMode = PeripheralMode.AUTO
    dependencies: list[str] = []
