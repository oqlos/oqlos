from .scenarios import router as scenarios_router
from .peripherals import router as peripherals_router
from .execution import router as execution_router
from .state import router as state_router
from .logs import router as logs_router
from .version import router as version_router
from .hardware import router as hardware_router

__all__ = [
    "scenarios_router",
    "peripherals_router",
    "execution_router",
    "state_router",
    "logs_router",
    "version_router",
    "hardware_router",
]
