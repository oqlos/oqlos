from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TypeVar

from fastapi.responses import FileResponse, HTMLResponse

T = TypeVar("T")


def serve_html_page(
    file_path: Path,
    *,
    missing_title: str,
    missing_message: str,
) -> HTMLResponse | FileResponse:
    """Serve a static HTML file when present, else return a small fallback page."""
    if file_path.exists():
        return FileResponse(
            file_path,
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
            },
        )
    return HTMLResponse(f"<h1>{missing_title}</h1><p>{missing_message}</p>")


def make_collection_route(
    route_name: str,
    get_collection: Callable[[], Mapping[str, T]],
):
    """Create a trivial list-all route for dict-backed state collections."""

    async def handler() -> list[T]:
        return list(get_collection().values())

    handler.__name__ = route_name
    return handler
