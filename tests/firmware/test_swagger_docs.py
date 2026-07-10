"""Regression: themed Swagger UI for /ui/api-docs iframe."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from oqlos.api.swagger_docs import register_swagger_routes, resolve_swagger_theme, swagger_theme_css_path


def test_resolve_swagger_theme_defaults_to_dark() -> None:
    class _Req:
        query_params = {}

    assert resolve_swagger_theme(_Req()) == "dark"  # type: ignore[arg-type]


def test_resolve_swagger_theme_reads_query() -> None:
    class _Req:
        query_params = {"theme": "high-contrast"}

    assert resolve_swagger_theme(_Req()) == "high-contrast"  # type: ignore[arg-type]


def test_swagger_dark_css_exists() -> None:
    path = swagger_theme_css_path("dark")
    assert path is not None
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert ".swagger-ui" in text
    assert "#0a0f1a" in text


def test_docs_injects_dark_stylesheet() -> None:
    app = FastAPI(title="Test", docs_url=None, redoc_url=None)
    register_swagger_routes(app)
    client = TestClient(app)
    response = client.get("/docs?theme=dark")
    assert response.status_code == 200
    assert "/docs-assets/swagger-dark.css" in response.text
    css = client.get("/docs-assets/swagger-dark.css")
    assert css.status_code == 200
    assert "text/css" in css.headers.get("content-type", "")
