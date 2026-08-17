"""
Test Simulator Backend Service - Refactored
Port: 8202 (Firmware Simulator)
"""
import argparse
from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
import sysconfig
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn

# Import refactored components
from oqlos.api.swagger_docs import register_swagger_routes
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
from oqlos.api.ui_prefs_routes import router as ui_prefs_router
from oqlos.api.update_status import router as update_status_router
from oqlos.api.oql_mqtt import oql_ws as _oql_ws_handler
from oqlos.api.oql_mqtt import router as oql_router, set_oql_controller
from oqlos.utils import load_sample_scenarios
from oqlos.utils.hui_scenario import register_hui_test_scenario
from oqlos.config import FIRMWARE_PORT, SERVICE_NAME, SERVICE_VERSION, get_settings
from oqlos.errors.fastapi_integration import install_oqlos_error_handler
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

NAVIGATION_PAGES = [
    {
        "path": "/ui/status",
        "label": "Status",
        "description": "BoardNet entrypoint: navigation, runtime health, adapters, USB, serial and I2C diagnostics.",
    },
    {
        "path": "/ui/hardware-modbus",
        "label": "Hardware Modbus",
        "description": "Modbus autodetect wizard, adapter configuration and IO/ADC bring-up.",
    },
    {
        "path": "/ui/hardware-coils",
        "label": "Coil TEST",
        "description": "Guarded, sequential DO1-DO8 wiring verification and detailed Modbus configuration.",
    },
    {
        "path": "/ui/hardware-rtc",
        "label": "Hardware RTC",
        "description": "Waveshare DS3231 RTC and watchdog diagnostics via piRTC sidecar.",
    },
    {
        "path": "/ui/motor-services",
        "label": "Motor services",
        "description": "Motor diagnostics, manual PWM/stepper tests, repair and sidecar status (Tic249, DRI0050).",
    },
    {
        "path": "/ui/scenario-files",
        "label": "Scenario files",
        "description": "OQL scenario editor served directly by OqlOS.",
    },
    {
        "path": "/ui/panel",
        "label": "OQL panel",
        "description": "Direct OQL command, scenario and manage verb tester.",
    },
    {
        "path": "/ui/editor",
        "label": "Legacy editor",
        "description": "Simple built-in scenario editor (redirects to scenario files).",
    },
    {
        "path": "/ui/api-docs",
        "label": "API docs",
        "description": "FastAPI Swagger embedded in the OqlOS UI shell.",
    },
    {
        "path": "/docs",
        "label": "API docs (raw)",
        "description": "FastAPI Swagger documentation (also embedded at /ui/api-docs).",
    },
]

NAVIGATION_ALIASES = [
    {"path": "/nav", "target": "/ui/status"},
    {"path": "/navigation", "target": "/ui/status"},
    {"path": "/status", "target": "/ui/status"},
    {"path": "/hardware-status", "target": "/ui/status"},
    {"path": "/restart", "target": "/ui/hardware-modbus"},
    {"path": "/hardware-restart", "target": "/ui/hardware-modbus"},
    {"path": "/modbus", "target": "/ui/hardware-modbus"},
    {"path": "/hardware-modbus", "target": "/ui/hardware-modbus"},
    {"path": "/hardware-coils", "target": "/ui/hardware-coils"},
    {"path": "/hardware-rtc", "target": "/ui/hardware-rtc"},
    {"path": "/rtc", "target": "/ui/hardware-rtc"},
    {"path": "/demo", "target": "/ui/motor-services"},
    {"path": "/hardware-demo", "target": "/ui/motor-services"},
    {"path": "/files", "target": "/ui/scenario-files"},
    {"path": "/scenario-files", "target": "/ui/scenario-files"},
    {"path": "/functions", "target": "/ui/func-editor"},
    {"path": "/func-editor", "target": "/ui/func-editor"},
    {"path": "/motor-services", "target": "/ui/motor-services"},
    {"path": "/panel", "target": "/ui/panel"},
    {"path": "/oql", "target": "/ui/panel"},
    {"path": "/oql-panel", "target": "/ui/panel"},
    {"path": "/editor", "target": "/ui/scenario-files"},
    {"path": "/api-docs", "target": "/ui/api-docs"},
]

NAVIGATION_API_ENDPOINTS = [
    {
        "method": "GET",
        "path": "/health",
        "description": "Service liveness for OqlOS firmware process.",
    },
    {
        "method": "GET",
        "path": "/api/v1/health",
        "description": "Versioned service liveness endpoint.",
    },
    {
        "method": "GET",
        "path": "/api/v1/navigation",
        "description": "Machine-readable page, API and alias index.",
    },
    {
        "method": "POST",
        "path": "/api/v1/oql/execute",
        "description": "Run OQL script/command in validate, dry-run or execute mode.",
    },
    {
        "method": "POST",
        "path": "/api/v1/oql/manage",
        "description": "Diagnostic/manage verbs such as health, identify, diagnose and usb-list.",
    },
    {
        "method": "GET",
        "path": "/api/v3/hardware/health",
        "description": "Hardware compatibility health used by migrated UI.",
    },
    {
        "method": "GET",
        "path": "/api/v3/hardware/configuration",
        "description": "Canonical effective hardware configuration (OQL/YAML/JSON).",
    },
    {
        "method": "GET",
        "path": "/api/v3/hardware/raspi-config",
        "description": "Declarative Raspberry Pi raspi-config (OQL/YAML/JSON).",
    },
    {
        "method": "WS",
        "path": "/ws/events/hardware",
        "description": "Hardware event stream.",
    },
    {
        "method": "WS",
        "path": "/ws/oql",
        "description": "OQL transport event stream.",
    },
]

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
        if hasattr(hardware, "enforce_motor2_startup_idle_state"):
            idle_ok = await hardware.enforce_motor2_startup_idle_state()
            if idle_ok:
                logger.info("Tic249 startup idle policy applied: deenergized")
            else:
                logger.error("Tic249 startup idle policy failed: motor may remain energized")
        try:
            from oqlos.hardware.startup_diagnostics import run_startup_diagnostics_and_repair

            await run_startup_diagnostics_and_repair()
        except Exception:  # pragma: no cover - startup diagnostics must never block boot
            logger.exception("Startup diagnostics wrapper failed")
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
    docs_url=None,
    redoc_url=None,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


install_oqlos_error_handler(app)
register_swagger_routes(app)

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
app.include_router(ui_prefs_router)
app.include_router(editor_router)
app.include_router(plugins_router.router)
app.include_router(oql_router)
app.include_router(update_status_router, prefix="/api/v1")

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

@app.get("/")
async def index_page(request: Request):
    return RedirectResponse(_with_query("/ui/status", request))


def _serve_static_html(relative_path: str, title: str, missing_message: str):
    return serve_html_page(
        STATIC_DIR / relative_path,
        missing_title=title,
        missing_message=missing_message,
    )

@app.get("/editor")
async def editor_page(request: Request):
    return RedirectResponse(_with_query("/ui/scenario-files", request))

@app.get("/panel")
async def panel_alias(request: Request):
    return _redirect_with_query("/ui/panel", request)


@app.get("/navigation")
async def navigation_alias(request: Request):
    return _redirect_with_query("/ui/status", request)


@app.get("/ui/legacy-panel", response_class=HTMLResponse)
async def ui_legacy_panel_page():
    return _serve_static_html("static/panel.html", "OqlOS Panel", "panel.html not found.")


@app.get("/ui/legacy-navigation", response_class=HTMLResponse)
async def ui_legacy_navigation_page():
    return _serve_static_html(
        "static/navigation.html",
        "OqlOS Navigation",
        "navigation.html not found.",
    )

# ---- Hardware/file UI moved in from c2004 connect-scenario (hardware-status,
# hardware-demo, hardware-restart, scenario-files, func-editor).
# The React hardware UI is built with Vite (base=/ui/).
# Hardware actuation flows through the OqlOS-owned /api/v3/hardware/* compatibility
# router, backed by the same gateway/plugin runtime as /api/v1/hardware/*.
def _resolve_ui_dist() -> Path:
    """Resolve Vite assets in a source checkout or an installed wheel."""
    checkout_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    installed_dist = Path(sysconfig.get_path("data")) / "frontend" / "dist"
    for candidate in (checkout_dist, installed_dist):
        if (candidate / "index.html").is_file():
            return candidate
    return checkout_dist


_UI_DIST = _resolve_ui_dist()


def _with_query(path: str, request: Request) -> str:
    query = str(request.url.query or "")
    return f"{path}?{query}" if query else path


def _redirect_with_query(path: str, request: Request):
    return RedirectResponse(_with_query(path, request))


@app.get("/hardware-status")
async def hardware_status_page(request: Request):
    return RedirectResponse(_with_query("/ui/status", request))


@app.get("/hardware-demo")
async def hardware_demo_alias(request: Request):
    return RedirectResponse(_with_query("/ui/motor-services", request))


@app.get("/hardware-restart")
async def hardware_restart_alias(request: Request):
    return RedirectResponse(_with_query("/ui/hardware-modbus", request))


@app.get("/hardware-modbus")
async def hardware_modbus_alias(request: Request):
    return RedirectResponse(_with_query("/ui/hardware-modbus", request))


@app.get("/hardware-coils")
async def hardware_coils_alias(request: Request):
    return RedirectResponse(_with_query("/ui/hardware-coils", request))


@app.get("/hardware-rtc")
async def hardware_rtc_alias(request: Request):
    return RedirectResponse(_with_query("/ui/hardware-rtc", request))


@app.get("/rtc")
async def rtc_alias(request: Request):
    return RedirectResponse(_with_query("/ui/hardware-rtc", request))


@app.get("/map-editor", include_in_schema=False)
@app.get("/map", include_in_schema=False)
async def retired_map_editor_alias() -> Response:
    return Response(status_code=404)


@app.get("/scenario-files")
@app.get("/scenario-files/{full_path:path}")
async def scenario_files_alias(request: Request):
    return RedirectResponse(_with_query("/ui/scenario-files", request))


@app.get("/func-editor")
@app.get("/func-editor/{full_path:path}")
async def func_editor_alias(request: Request):
    return RedirectResponse(_with_query("/ui/func-editor", request))


@app.get("/motor-services")
async def motor_services_alias(request: Request):
    return RedirectResponse(_with_query("/ui/motor-services", request))


@app.get("/nav")
async def nav_alias(request: Request):
    return _redirect_with_query("/ui/status", request)


@app.get("/status")
async def status_alias(request: Request):
    return _redirect_with_query("/ui/status", request)


@app.get("/restart")
async def restart_alias(request: Request):
    return _redirect_with_query("/ui/hardware-modbus", request)


@app.get("/modbus")
async def modbus_alias(request: Request):
    return _redirect_with_query("/ui/hardware-modbus", request)


@app.get("/demo")
async def demo_alias(request: Request):
    return _redirect_with_query("/ui/motor-services", request)


@app.get("/files")
async def files_alias(request: Request):
    return _redirect_with_query("/ui/scenario-files", request)


@app.get("/functions")
async def functions_alias(request: Request):
    return _redirect_with_query("/ui/func-editor", request)


@app.get("/api-docs")
async def api_docs_alias(request: Request):
    return _redirect_with_query("/ui/api-docs", request)


@app.get("/oql")
@app.get("/oql-panel")
async def oql_panel_alias(request: Request):
    return _redirect_with_query("/ui/panel", request)

if (_UI_DIST / "assets").is_dir():
    app.mount("/ui/assets", StaticFiles(directory=_UI_DIST / "assets"), name="ui-assets")


@app.get("/ui/navigation")
@app.get("/ui/hardware-status")
async def ui_legacy_status_routes(request: Request):
    return _redirect_with_query("/ui/status", request)


@app.get("/ui/map-editor", include_in_schema=False)
async def retired_ui_map_editor() -> Response:
    return Response(status_code=404)


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


@app.get("/update", response_class=HTMLResponse, include_in_schema=False)
async def update_status_page():
    from oqlos.api.update_status import UPDATE_PAGE

    return serve_html_page(
        UPDATE_PAGE,
        missing_title="OqlOS — status wdrożenia",
        missing_message="Brak pliku static/update/index.html.",
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


@app.get("/api/v1/navigation")
async def navigation_index(request: Request):
    """Machine-readable BoardNet/OqlOS UI and API index."""
    settings = get_settings()
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "node_id": settings.oql_node_id,
        "role": settings.oql_transport_role,
        "base_url": str(request.base_url).rstrip("/"),
        "pages": NAVIGATION_PAGES,
        "api": NAVIGATION_API_ENDPOINTS,
        "aliases": NAVIGATION_ALIASES,
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
