"""Regression: all human OqlOS pages live under /ui/* with legacy redirects."""

from __future__ import annotations

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
    assert navigation.headers["location"] == "/ui/navigation"


def test_ui_panel_and_navigation_serve_html(client: TestClient) -> None:
    panel = client.get("/ui/panel")
    assert panel.status_code == 200
    assert "Panel testowy" in panel.text or "OqlOS" in panel.text

    navigation = client.get("/ui/navigation")
    assert navigation.status_code == 200
    assert "OqlOS BoardNet navigation" in navigation.text


def test_navigation_index_lists_ui_prefixed_pages(client: TestClient) -> None:
    body = client.get("/api/v1/navigation").json()
    page_paths = {item["path"] for item in body["pages"]}
    assert "/ui/navigation" in page_paths
    assert "/ui/panel" in page_paths
    assert "/ui/hardware-restart" in page_paths
    assert "/navigation" not in page_paths
    assert "/panel" not in page_paths

    aliases = {item["path"]: item["target"] for item in body["aliases"]}
    assert aliases["/panel"] == "/ui/panel"
    assert aliases["/oql"] == "/ui/panel"
    assert aliases["/status"] == "/ui/hardware-status"
