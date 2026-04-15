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

# Import refactored components
from oqlos.core.state import StateManager
from oqlos.core.executor import ScenarioOrchestrator
from oqlos.hardware.plugin_gateway import PluginHardwareGateway
from oqlos.api import (
    scenarios_router,
    peripherals_router,
    execution_router,
    state_router,
    logs_router,
    version_router,
    hardware_router,
)
from oqlos.api.editor import router as editor_router
from oqlos.api import plugins as plugins_router
from oqlos.api.utils.execution_ctrl import set_dependencies as set_shared_dependencies
from oqlos.api.hardware import set_hardware_gateway
from oqlos.utils import load_sample_scenarios
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
hardware = PluginHardwareGateway()
state_manager = StateManager()
orchestrator = ScenarioOrchestrator(state_manager, hardware)

# Set dependencies for API modules — single shared injection point
set_shared_dependencies(state_manager, orchestrator)
set_hardware_gateway(hardware)

# Include API routers
app.include_router(scenarios_router)
app.include_router(peripherals_router)
app.include_router(execution_router)
app.include_router(state_router)
app.include_router(logs_router)
app.include_router(version_router)
app.include_router(hardware_router)
app.include_router(editor_router)
app.include_router(plugins_router.router)

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

@app.get("/editor", response_class=HTMLResponse)
async def editor_page():
    """Serve the scenario editor UI"""
    editor_path = STATIC_DIR / "static" / "editor.html"
    if editor_path.exists():
        return FileResponse(editor_path)
    return HTMLResponse("<h1>Scenario Editor</h1><p>editor.html not found.</p>")

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

def run():
    """Entry point for ``oqlos-server`` console script."""
    uvicorn.run(app, host="0.0.0.0", port=FIRMWARE_PORT)


if __name__ == "__main__":
    run()
