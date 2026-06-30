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

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
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
from oqlos.api.hardware_v3 import router as hardware_v3_router
from oqlos.api.hardware_v3 import hardware_events_ws as _hardware_events_ws_handler
from oqlos.api.oql_mqtt import router as oql_router, set_oql_controller, oql_ws as _oql_ws_handler
from oqlos.utils import load_sample_scenarios
from oqlos.utils.hui_scenario import register_hui_test_scenario
from oqlos.config import FIRMWARE_PORT, SERVICE_NAME, SERVICE_VERSION, get_settings
from oqlos.shared._endpoint_helpers import serve_html_page

if TYPE_CHECKING:
    from oqlos.hardware.plugin_gateway import PluginHardwareGateway

from oqlos.shared.logger import configure_oqlos_logging, get_logger

configure_oqlos_logging()
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
    if hardware is not None and hasattr(hardware, "ensure_initialized"):
        logger.info("Awaiting hardware plugin initialization…")
        await hardware.ensure_initialized()
        summary = getattr(hardware, "last_init_summary", None)
        if isinstance(summary, dict):
            logger.info(
                "Hardware init summary: connected=%s failed=%s disabled=%s",
                summary.get("connected"),
                summary.get("failed"),
                summary.get("disabled"),
            )
    await _start_oql_transport()
    try:
        yield
    finally:
        await _stop_oql_transport()


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

# OQL-over-MQTT transport endpoints (created in lifespan when a role is selected).
_oql_controller = None
_oql_agent = None

# Include API routers
app.include_router(scenarios_router)
app.include_router(peripherals_router)
app.include_router(execution_router)
app.include_router(state_router)
app.include_router(logs_router)
app.include_router(version_router)
app.include_router(hardware_router)
app.include_router(hardware_v3_router)
app.include_router(editor_router)
app.include_router(plugins_router.router)
app.include_router(oql_router)

# Compatibility: expose the same API under /firmware/* (frontend expects this prefix)
app.include_router(scenarios_router, prefix="/firmware")
app.include_router(peripherals_router, prefix="/firmware")
app.include_router(execution_router, prefix="/firmware")
app.include_router(state_router, prefix="/firmware")
app.include_router(logs_router, prefix="/firmware")
app.include_router(version_router, prefix="/firmware")
app.include_router(hardware_router, prefix="/firmware")
app.include_router(hardware_v3_router, prefix="/firmware")
app.include_router(oql_router, prefix="/firmware")

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
    register_hui_test_scenario(state_manager)


async def _start_oql_transport() -> None:
    """Start the OQL-over-MQTT controller and/or agent per configured role.

    role: off (default) | controller | agent | both. ``off`` is a no-op so the
    single-process behavior is unchanged.
    """
    global _oql_controller, _oql_agent

    settings = get_settings()
    role = (settings.oql_transport_role or "off").strip().lower()
    if role == "off":
        return

    from oqlos.hardware.transport.mqtt_oql_bridge import OqlMqttController, OqlMqttAgent

    broker = dict(
        host=settings.oql_mqtt_host,
        port=settings.oql_mqtt_port,
        node_id=settings.oql_node_id,
        topic_prefix=settings.oql_topic_prefix,
        username=settings.oql_mqtt_username or None,
        password=settings.oql_mqtt_password or None,
    )

    if role in ("controller", "both"):
        _oql_controller = OqlMqttController(
            default_timeout_ms=settings.oql_default_timeout_ms, **broker
        )
        await _oql_controller.start()
        set_oql_controller(_oql_controller)
        logger.info("OQL transport: controller started (node=%s)", settings.oql_node_id)

    if role in ("agent", "both"):
        if hardware is None:
            logger.error("OQL transport: agent role needs an initialized hardware gateway")
        else:
            _oql_agent = OqlMqttAgent(gateway=hardware, **broker)
            await _oql_agent.start()
            logger.info("OQL transport: agent started (node=%s)", settings.oql_node_id)


async def _stop_oql_transport() -> None:
    global _oql_controller, _oql_agent
    if _oql_agent is not None:
        await _oql_agent.stop()
        _oql_agent = None
    if _oql_controller is not None:
        await _oql_controller.stop()
        _oql_controller = None
    set_oql_controller(None)

# ============= Basic Endpoints =============

@app.get("/", response_class=HTMLResponse)
async def index_page():
    return _serve_static_html("index.html", "Test Simulator Firmware", "index.html not found.")


def _serve_static_html(relative_path: str, title: str, missing_message: str):
    return serve_html_page(
        STATIC_DIR / relative_path,
        missing_title=title,
        missing_message=missing_message,
    )

@app.get("/editor", response_class=HTMLResponse)
async def editor_page():
    return _serve_static_html("static/editor.html", "Scenario Editor", "editor.html not found.")

@app.get("/panel", response_class=HTMLResponse)
async def panel_page():
    return _serve_static_html("static/panel.html", "OqlOS Panel", "panel.html not found.")

# ---- Hardware UI SPA moved in from c2004 connect-scenario (hardware-status,
# hardware-demo, hardware-restart, map-editor). Built with Vite (base=/ui/).
# Hardware actuation flows through the OqlOS-owned /api/v3/hardware/* compatibility
# router, backed by the same gateway/plugin runtime as /api/v1/hardware/*.
_UI_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _with_query(path: str, request: Request) -> str:
    query = str(request.url.query or "")
    return f"{path}?{query}" if query else path


@app.get("/hardware-status", response_class=HTMLResponse)
async def hardware_status_page():
    return _serve_static_html("static/hardware-status.html", "OqlOS Hardware Status", "hardware-status.html not found.")


@app.get("/hardware-demo")
async def hardware_demo_alias(request: Request):
    return RedirectResponse(_with_query("/ui/hardware-demo", request))


@app.get("/hardware-restart")
async def hardware_restart_alias(request: Request):
    return RedirectResponse(_with_query("/ui/hardware-restart", request))


@app.get("/map-editor")
async def map_editor_alias(request: Request):
    return RedirectResponse(_with_query("/ui/map-editor", request))

if (_UI_DIST / "assets").is_dir():
    app.mount("/ui/assets", StaticFiles(directory=_UI_DIST / "assets"), name="ui-assets")


@app.get("/ui", response_class=HTMLResponse)
@app.get("/ui/{full_path:path}", response_class=HTMLResponse)
async def hardware_ui_spa(full_path: str = ""):
    """Serve the moved hardware UI SPA, falling back to index.html for client routes."""
    if full_path:
        candidate = (_UI_DIST / full_path).resolve()
        if candidate.is_file() and str(candidate).startswith(str(_UI_DIST)):
            return FileResponse(candidate)
    index = _UI_DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    return HTMLResponse(
        "<h1>OqlOS hardware UI not built</h1>"
        "<p>Run <code>npm --prefix frontend install &amp;&amp; npm --prefix frontend run build</code>.</p>",
        status_code=503,
    )


@app.get("/health")
@app.get("/api/v1/health")
@app.get("/firmware/api/v1/health")
async def health_check():
    """Health check endpoint for tests and frontend compatibility probes."""
    return {
        "status": "ok",
        "healthy": True,
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

async def _forward_websocket(websocket: WebSocket, handler) -> None:
    await handler(websocket)


@app.websocket("/ws/events/hardware")
async def hardware_events_websocket_alias(websocket: WebSocket):
    await _forward_websocket(websocket, _hardware_events_ws_handler)


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


@app.websocket("/ws/oql")
async def oql_websocket_alias(websocket: WebSocket):
    await _forward_websocket(websocket, _oql_ws_handler)

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
