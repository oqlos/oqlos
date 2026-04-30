"""
Test Simulator Backend Service - Refactored
Port: 8202 (Firmware Simulator)
"""
import argparse
from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

# Import refactored components
from oqlos.core.state import StateManager
from oqlos.core.executor import ScenarioOrchestrator
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
from oqlos.api.plugins import ensure_plugins_initialized
from oqlos.api.utils.execution_ctrl import set_dependencies as set_shared_dependencies
from oqlos.api.hardware import set_hardware_gateway
from oqlos.utils import load_sample_scenarios
from oqlos.config import FIRMWARE_PORT, SERVICE_NAME, SERVICE_VERSION
from oqlos.shared._endpoint_helpers import serve_html_page

if TYPE_CHECKING:
    from oqlos.hardware.plugin_gateway import PluginHardwareGateway

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

@asynccontextmanager
async def _app_lifespan(_: FastAPI):
    _initialize_runtime_dependencies()
    yield


# Create FastAPI app
app = FastAPI(
    title="Test Simulator Backend",
    version=SERVICE_VERSION,
    lifespan=_app_lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Runtime dependencies are initialized lazily on app startup.
hardware: "PluginHardwareGateway | None" = None
state_manager: StateManager | None = None
orchestrator: ScenarioOrchestrator | None = None

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

def _initialize_runtime_dependencies() -> None:
    """Initialize runtime dependency graph once per process."""
    global hardware, state_manager, orchestrator

    if hardware is not None and state_manager is not None and orchestrator is not None:
        return

    logger.info("Initializing OqlOS runtime dependencies")
    ensure_plugins_initialized()

    from oqlos.hardware.plugin_gateway import PluginHardwareGateway

    hardware = PluginHardwareGateway()
    state_manager = StateManager()
    orchestrator = ScenarioOrchestrator(state_manager, hardware)

    set_shared_dependencies(state_manager, orchestrator)
    set_hardware_gateway(hardware)
    load_sample_scenarios(state_manager)

# ============= Basic Endpoints =============

@app.get("/", response_class=HTMLResponse)
async def index_page():
    """Serve the firmware UI (index.html) at root"""
    return serve_html_page(
        STATIC_DIR / "index.html",
        missing_title="Test Simulator Firmware",
        missing_message="index.html not found.",
    )

@app.get("/editor", response_class=HTMLResponse)
async def editor_page():
    """Serve the scenario editor UI"""
    return serve_html_page(
        STATIC_DIR / "static" / "editor.html",
        missing_title="Scenario Editor",
        missing_message="editor.html not found.",
    )

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
    if state_manager is None:
        await websocket.close(code=1011)
        return

    manager = state_manager
    await websocket.accept()
    manager.websocket_connections.append(websocket)
    
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
        if websocket in manager.websocket_connections:
            manager.websocket_connections.remove(websocket)

def _parse_server_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="oqlos-server",
        description="Run OqlOS API/runtime server",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=FIRMWARE_PORT,
        help=f"Bind port (default from env/config: {FIRMWARE_PORT})",
    )
    return parser.parse_args()


def run():
    """Entry point for ``oqlos-server`` console script."""
    args = _parse_server_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    run()
