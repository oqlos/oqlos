"""Theme-aware Swagger UI for OqlOS (embedded in /ui/api-docs iframe)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_SWAGGER_THEMES = {
    "dark": "swagger-dark.css",
    "high-contrast": "swagger-high-contrast.css",
}
_SUPPORTED_THEMES = frozenset({"light", "dark", "high-contrast"})


def resolve_swagger_theme(request: Request) -> str:
    theme = (request.query_params.get("theme") or "dark").strip().lower()
    if theme in _SUPPORTED_THEMES:
        return theme
    return "dark"


def themed_swagger_ui_html(request: Request, *, openapi_url: str, title: str) -> HTMLResponse:
    theme = resolve_swagger_theme(request)
    swagger_ui_parameters = {
        "syntaxHighlight.theme": "agate" if theme == "light" else "monokai",
        "docExpansion": "list",
        "filter": True,
    }
    response = get_swagger_ui_html(
        openapi_url=openapi_url,
        title=title,
        swagger_ui_parameters=swagger_ui_parameters,
        oauth2_redirect_url=str(request.url_for("swagger_ui_redirect")),
    )
    override_href = _SWAGGER_THEMES.get(theme)
    if not override_href:
        return response
    body = response.body.decode(response.charset or "utf-8")
    link = f'<link type="text/css" rel="stylesheet" href="/docs-assets/{override_href}">'
    body = body.replace("</head>", f"    {link}\n    </head>", 1)
    return HTMLResponse(content=body, status_code=response.status_code)


def register_swagger_routes(app: FastAPI) -> None:
    if _STATIC_DIR.is_dir():
        app.mount("/docs-assets", StaticFiles(directory=_STATIC_DIR), name="docs-assets")

    @app.get("/docs", include_in_schema=False, name="swagger_ui")
    async def swagger_ui(request: Request) -> HTMLResponse:
        return themed_swagger_ui_html(
            request,
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
        )

    @app.get("/docs/oauth2-redirect", include_in_schema=False, name="swagger_ui_redirect")
    async def swagger_ui_redirect() -> HTMLResponse:
        return get_swagger_ui_oauth2_redirect_html()


def swagger_theme_css_path(theme: str) -> Path | None:
    filename = _SWAGGER_THEMES.get(theme)
    if not filename:
        return None
    return _STATIC_DIR / filename


__all__ = [
    "register_swagger_routes",
    "resolve_swagger_theme",
    "swagger_theme_css_path",
    "themed_swagger_ui_html",
]
