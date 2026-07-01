"""FastAPI glue for OqlosError — kept separate from exceptions.py so importing
OqlosError elsewhere (CLI, tests, non-FastAPI code) doesn't require fastapi.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from oqlos.errors.exceptions import OqlosError


def install_oqlos_error_handler(app: FastAPI) -> None:
    """Register the standard OqlIssue JSON response for any raised OqlosError.

    Exception handlers are FastAPI-app-scoped, not router-scoped — any app
    that mounts a router which can raise OqlosError (e.g. oql_mqtt's router)
    must call this, not just the main production app.
    """

    @app.exception_handler(OqlosError)
    async def _oqlos_error_handler(request: Request, exc: OqlosError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_issue())
