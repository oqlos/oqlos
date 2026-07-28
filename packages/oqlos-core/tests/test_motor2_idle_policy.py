"""Execution-level regression tests for the Tic249 idle policy."""

from __future__ import annotations

from oqlos.core import _action_motor2


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _Client:
    def __init__(self) -> None:
        self.posts: list[tuple[str, dict[str, object] | None]] = []

    def __enter__(self) -> "_Client":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def post(
        self,
        path: str,
        json: dict[str, object] | None = None,
    ) -> _Response:
        self.posts.append((path, json))
        return _Response({"success": True})


def test_stop_releases_tic249_coils(monkeypatch) -> None:
    client = _Client()
    monkeypatch.setattr(_action_motor2, "lung_motor_url", lambda: "http://tic249")
    monkeypatch.setattr(_action_motor2.httpx, "Client", lambda **_kwargs: client)

    _action_motor2._post_motor2_stop()

    assert client.posts == [
        ("/api/stop", None),
        ("/api/energize", {"enable": False}),
    ]
