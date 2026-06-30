"""Regression tests for gateway HTTP helpers."""

from __future__ import annotations

import asyncio

from oqlos.hardware import gateway_http


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Client:
  def __init__(self):
    self.calls = []

  async def get(self, url):
    self.calls.append(("GET", url))
    return _Response({"channel": 1})

  async def post(self, url, json=None):
    self.calls.append(("POST", url, json))
    return _Response({"ok": True})


def test_gateway_get_json(monkeypatch):
  client = _Client()

  class _Ctx:
    async def __aenter__(self):
      return client

    async def __aexit__(self, *args):
      return False

  monkeypatch.setattr(gateway_http.httpx, "AsyncClient", lambda timeout: _Ctx())

  payload = asyncio.run(gateway_http.get_json("http://localhost:8080", "/read/0"))

  assert payload == {"channel": 1}
  assert client.calls[0][0] == "GET"
  assert client.calls[0][1] == "http://localhost:8080/read/0"
