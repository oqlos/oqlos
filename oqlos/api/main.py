"""
Test Simulator Backend Service - Refactored
Port: 8202 (Firmware Simulator)
"""
import json
import logging
import sys
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn

_firmware_root = Path(__file__).parent
_project_root = _firmware_root.parent
if str(_firmware_root) not in sys.path:
    sys.path.insert(0, str(_firmware_root))
if str(_project_root) not in sys.path:
    sys.path.append(str(_project_root))

for _module_name in [name for name in list(sys.modules) if name == "api" or name.startswith("api.")]:
    sys.modules.pop(_module_name, None)
for _module_name in [name for name in list(sys.modules) if name == "models" or name.startswith("models.")]:
    sys.modules.pop(_module_name, None)

# Import refactored components
from services import StateManager, ScenarioOrchestrator, HardwareGateway
from api import (
    scenarios_router,
    peripherals_router,
    execution_router,
    state_router,
    logs_router,
    version_router,
    hardware_router,
)
from api.scenarios import set_state_manager as set_scenarios_state_manager
from api.peripherals import set_state_manager as set_peripherals_state_manager
from api.execution import set_dependencies as set_execution_dependencies
from api.state import set_dependencies as set_state_dependencies
from api.hardware import set_hardware_gateway
from utils import load_sample_scenarios
from oqlos.config import FIRMWARE_PORT, SERVICE_NAME, SERVICE_VERSION

logging.basicConfig(level=logging.INFO)
try:
    from oqlos.shared.logger import get_logger  # type: ignore
except ModuleNotFoundError:
    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)

logger = get_logger(__name__)

# Initialize nfo logging (safe fallback if not installed)
try:
    from nfo_config import setup_nfo
    setup_nfo()
except ImportError:
    pass

STATIC_DIR = Path(__file__).parent

# Create FastAPI app
app = FastAPI(title="Test Simulator Backend", version=SERVICE_VERSION)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
hardware = HardwareGateway()
state_manager = StateManager()
orchestrator = ScenarioOrchestrator(state_manager, hardware)

# Set dependencies for API modules
set_scenarios_state_manager(state_manager)
set_peripherals_state_manager(state_manager)
set_execution_dependencies(state_manager, orchestrator)
set_state_dependencies(state_manager, orchestrator)
set_hardware_gateway(hardware)

# Include API routers
app.include_router(scenarios_router)
app.include_router(peripherals_router)
app.include_router(execution_router)
app.include_router(state_router)
app.include_router(logs_router)
app.include_router(version_router)
app.include_router(hardware_router)

# Compatibility: expose the same API under /firmware/* (frontend expects this prefix)
app.include_router(scenarios_router, prefix="/firmware")
app.include_router(peripherals_router, prefix="/firmware")
app.include_router(execution_router, prefix="/firmware")
app.include_router(state_router, prefix="/firmware")
app.include_router(logs_router, prefix="/firmware")
app.include_router(version_router, prefix="/firmware")
app.include_router(hardware_router, prefix="/firmware")

# Load sample data
load_sample_scenarios(state_manager)

# ============= Basic Endpoints =============

@app.get("/", response_class=HTMLResponse)
async def index_page():
    """Serve the firmware UI (index.html) at root"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>Test Simulator Firmware</h1><p>index.html not found.</p>")

@app.get("/health")
@app.get("/api/v1/health")
@app.get("/firmware/api/v1/health")
async def health_check():
    """Health check endpoint for tests and frontend compatibility probes."""
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "port": FIRMWARE_PORT,
    }

@app.get("/api/status")
async def status():
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "port": FIRMWARE_PORT,
        "status": "running",
    }

# ============= WebSocket Endpoint =============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state_manager.websocket_connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get('type') == 'subscribe':
                    channels = message.get('channels', [])
                    await websocket.send_json({
                        'type': 'subscribed',
                        'channels': channels
                    })
            except json.JSONDecodeError:
                await websocket.send_json({'error': 'Invalid JSON'})
    
    except WebSocketDisconnect:
        state_manager.websocket_connections.remove(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=FIRMWARE_PORT)
