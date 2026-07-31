"""Regression: all human OqlOS pages live under /ui/* with legacy redirects."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from oqlos.api.main import app

    return TestClient(app)


def test_legacy_panel_and_navigation_redirect_to_ui(client: TestClient) -> None:
    panel = client.get("/panel?mode=dry-run", follow_redirects=False)
    assert panel.status_code in {302, 307}
    assert panel.headers["location"] == "/ui/panel?mode=dry-run"

    navigation = client.get("/navigation", follow_redirects=False)
    assert navigation.status_code in {302, 307}
    assert navigation.headers["location"] == "/ui/status"


def test_ui_panel_and_status_serve_html(client: TestClient) -> None:
    panel = client.get("/ui/panel")
    assert panel.status_code == 200
    # Both now serve the React SPA shell — content is rendered client-side
    assert '<div id="root">' in panel.text

    status = client.get("/ui/status")
    assert status.status_code == 200
    assert '<div id="root">' in status.text

    legacy_navigation = client.get("/ui/navigation", follow_redirects=False)
    assert legacy_navigation.status_code in {302, 307}
    assert legacy_navigation.headers["location"] == "/ui/status"


def test_navigation_index_lists_ui_prefixed_pages(client: TestClient) -> None:
    body = client.get("/api/v1/navigation").json()
    page_paths = {item["path"] for item in body["pages"]}
    assert "/ui/status" in page_paths
    assert "/ui/panel" in page_paths
    assert "/ui/hardware-modbus" in page_paths
    assert "/ui/hardware-rtc" in page_paths
    assert "/ui/func-editor" not in page_paths
    assert "/navigation" not in page_paths
    assert "/panel" not in page_paths

    aliases = {item["path"]: item["target"] for item in body["aliases"]}
    assert aliases["/panel"] == "/ui/panel"
    assert aliases["/oql"] == "/ui/panel"
    assert aliases["/status"] == "/ui/status"
    assert aliases["/functions"] == "/ui/func-editor"


def test_ui_func_editor_redirects_to_ui_func_editor(client: TestClient) -> None:
    response = client.get("/func-editor?lang=pl", follow_redirects=False)
    assert response.status_code in {302, 307}
    assert response.headers["location"] == "/ui/func-editor?lang=pl"


def test_function_editor_is_not_linked_from_static_navigation() -> None:
    static_dir = Path(__file__).resolve().parents[2] / "oqlos" / "api"
    menu_files = [
        static_dir / "index.html",
        static_dir / "static" / "navigation.html",
        static_dir / "static" / "hardware-status.html",
        static_dir / "static" / "editor.html",
        static_dir / "static" / "panel.html",
    ]

    for menu_file in menu_files:
        assert 'href="/ui/func-editor"' not in menu_file.read_text(encoding="utf-8")
