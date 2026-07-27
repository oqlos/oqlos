"""RFC 9457 / C2004 error boundary for the standalone OqlOS API.

The local OqlIssue code is useful for hardware diagnosis, but is not a public
API error code.  Every HTTP failure therefore exposes a canonical ``C2004-*``
code and keeps the granular identifier under
``metadata.diagnostics.issue_code``.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from oqlos.errors.c2004_catalog_generated import CATALOG
from oqlos.errors.exceptions import OqlosError

logger = logging.getLogger(__name__)

_STATUS_CODE_MAP = {
    400: "C2004-DATA-0002",
    401: "C2004-AUTH-0001",
    403: "C2004-AUTH-0002",
    404: "C2004-DATA-0001",
    409: "C2004-DATA-0003",
    422: "C2004-DATA-0002",
    502: "C2004-NET-0001",
    503: "C2004-NET-0002",
    504: "C2004-NET-0003",
}


def _correlation_id(request: Request) -> str:
    return (
        request.headers.get("x-correlation-id")
        or request.headers.get("x-request-id")
        or f"cor-{uuid4().hex[:12]}"
    )


def _public_code_for_status(status_code: int) -> str:
    return _STATUS_CODE_MAP.get(int(status_code), "C2004-SYS-0000")


def _problem_response(
    request: Request,
    *,
    public_code: str,
    status_code: int,
    message: str,
    context: Any = None,
    diagnostics: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    correlation_id: str | None = None,
) -> JSONResponse:
    entry = CATALOG.get(public_code) or CATALOG["C2004-SYS-0000"]
    public_code = entry.code
    correlation_id = correlation_id or _correlation_id(request)
    occurrence_id = str(uuid4())
    base_url = str(request.base_url).rstrip("/")
    metadata: dict[str, Any] = {
        "domain": entry.domain,
        "severity": entry.severity,
        "classification": entry.classification,
        "confidentiality": entry.confidentiality,
        "retryable": entry.retryable,
        "owner": entry.owner,
        "correlation_id": correlation_id,
        "docs": f"/api/v3/errors/catalog/{public_code}",
        "remediation": entry.remediation,
    }
    if context not in (None, {}, []):
        metadata["context"] = jsonable_encoder(context)
    if diagnostics:
        metadata["diagnostics"] = jsonable_encoder(diagnostics)

    content = {
        "type": f"{base_url}/api/v3/errors/catalog/{public_code}",
        "title": entry.title,
        "status": int(status_code),
        "detail": message,
        "instance": f"{base_url}/api/v3/errors/occurrences/{occurrence_id}",
        "code": public_code,
        "slug": entry.slug,
        "domain": entry.domain,
        "severity": entry.severity,
        "classification": entry.classification,
        "confidentiality": entry.confidentiality,
        "retryable": entry.retryable,
        "owner": entry.owner,
        "correlation_id": correlation_id,
        "error_code": public_code,
        "success": False,
        "ok": False,
        "error": message,
        "remediation": entry.remediation,
        "metadata": metadata,
    }
    response_headers = dict(headers or {})
    response_headers["X-Correlation-ID"] = correlation_id
    return JSONResponse(
        status_code=int(status_code),
        content=content,
        headers=response_headers,
        media_type="application/problem+json",
    )


def install_oqlos_error_handler(app: FastAPI) -> None:
    """Register the shared C2004 response boundary for all HTTP failures.

    Exception handlers are FastAPI-app-scoped, not router-scoped — any app
    that mounts a router which can raise OqlosError (e.g. oql_mqtt's router)
    must call this, not just the main production app.
    """

    @app.exception_handler(OqlosError)
    async def _oqlos_error_handler(request: Request, exc: OqlosError) -> JSONResponse:
        diagnostics: dict[str, Any] = {
            "issue_code": exc.issue_code,
            "issue_domain": exc.domain,
            "issue_severity": exc.severity,
        }
        if exc.repair is not None:
            diagnostics["repair"] = {
                "id": exc.repair.id,
                "scope": exc.repair.scope,
                "auto_executable": exc.repair.auto_executable,
                "actuation_risk": exc.repair.actuation_risk,
                "hint": exc.repair.hint,
            }
        return _problem_response(
            request,
            public_code=exc.public_code,
            status_code=exc.status_code,
            message=exc.message,
            context=exc.detail,
            diagnostics=diagnostics,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail = exc.detail
        context: Any = detail if isinstance(detail, (dict, list)) else None
        public_code = ""
        message = str(detail)
        diagnostics: dict[str, Any] | None = None
        if isinstance(detail, dict):
            candidate = str(
                detail.get("error_code") or detail.get("c2004_code") or ""
            )
            if candidate in CATALOG:
                public_code = candidate
            message = str(detail.get("message") or detail.get("error") or message)
            issue_code = detail.get("issue_code")
            if issue_code:
                diagnostics = {"issue_code": str(issue_code)}
        return _problem_response(
            request,
            public_code=public_code or _public_code_for_status(exc.status_code),
            status_code=exc.status_code,
            message=message,
            context=context,
            diagnostics=diagnostics,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _problem_response(
            request,
            public_code="C2004-DATA-0002",
            status_code=422,
            message="Request validation failed",
            context={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = _correlation_id(request)
        logger.exception(
            "Uncoded OqlOS API failure correlation_id=%s path=%s",
            correlation_id,
            request.url.path,
            exc_info=exc,
        )
        return _problem_response(
            request,
            public_code="C2004-SYS-0000",
            status_code=500,
            message=CATALOG["C2004-SYS-0000"].message,
            diagnostics={"exception_type": type(exc).__name__},
            correlation_id=correlation_id,
        )
