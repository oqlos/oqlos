"""RFC 9457 / C2004 error boundary for the standalone OqlOS API.

The local OqlIssue code is useful for hardware diagnosis, but is not a public
API error code.  Every HTTP failure therefore exposes a canonical ``C2004-*``
code and keeps the granular identifier under
``metadata.diagnostics.issue_code``.
"""

from __future__ import annotations

import logging
import re
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
    400: "C2004-DATA-0004",
    401: "C2004-AUTH-0001",
    403: "C2004-AUTH-0002",
    404: "C2004-DATA-0001",
    409: "C2004-DATA-0003",
    422: "C2004-DATA-0002",
    429: "C2004-AUTH-0003",
    502: "C2004-NET-0001",
    503: "C2004-NET-0002",
    504: "C2004-NET-0003",
}
_CORRELATION_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_UPSTREAM_LABEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}")
_UPSTREAM_PATH_PATTERN = re.compile(r"/[A-Za-z0-9._~/-]{1,255}")


def _safe_correlation_id(value: object) -> str | None:
    candidate = str(value or "").strip()
    return candidate if _CORRELATION_ID_PATTERN.fullmatch(candidate) else None


def correlation_id_for_request(request: Request) -> str:
    """Resolve one correlation id at the public HTTP boundary."""
    return (
        _safe_correlation_id(request.headers.get("x-correlation-id"))
        or _safe_correlation_id(request.headers.get("x-request-id"))
        or f"cor-{uuid4().hex[:12]}"
    )


def _safe_upstream_context(
    detail: dict[str, Any], upstream: dict[str, Any]
) -> dict[str, str]:
    metadata = upstream.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    upstream_context = metadata.get("context")
    upstream_context = upstream_context if isinstance(upstream_context, dict) else {}

    def label(value: object, fallback: str) -> str:
        candidate = str(value or "").strip()
        return (
            candidate
            if _UPSTREAM_LABEL_PATTERN.fullmatch(candidate)
            else fallback
        )

    path = str(detail.get("path") or "").strip()
    target = (
        f"oqlos-api://configured-target{path}"
        if _UPSTREAM_PATH_PATTERN.fullmatch(path)
        else "oqlos-api://configured-target"
    )
    return {
        "architecture": label(upstream.get("architecture"), "SOA"),
        "layer": label(upstream.get("layer"), "upstream"),
        "component": label(upstream.get("component"), "upstream-api"),
        "stage": label(upstream.get("stage"), "upstream.response"),
        "problem_source": "upstream",
        "operation_id": label(upstream_context.get("operation_id"), "upstream.request"),
        "upstream_target": target,
    }


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
    if int(status_code) != entry.http_status:
        logger.warning(
            "Normalizing mismatched HTTP status for %s: received=%s catalog=%s",
            public_code,
            status_code,
            entry.http_status,
        )
    status_code = entry.http_status
    correlation_id = (
        _safe_correlation_id(correlation_id) or correlation_id_for_request(request)
    )
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
    context_dict = context if isinstance(context, dict) else {}
    diagnostics_dict = diagnostics if isinstance(diagnostics, dict) else {}
    architecture = str(
        diagnostics_dict.get("architecture")
        or context_dict.get("architecture")
        or "SOA"
    )
    layer = str(
        diagnostics_dict.get("layer")
        or context_dict.get("layer")
        or "oqlos"
    )
    component = str(
        diagnostics_dict.get("component")
        or context_dict.get("component")
        or context_dict.get("plugin_id")
        or "oqlos-api"
    )
    stage = str(
        diagnostics_dict.get("stage")
        or context_dict.get("stage")
        or "api.error"
    )
    metadata.update(
        architecture=architecture,
        layer=layer,
        component=component,
        stage=stage,
    )
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
        "architecture": architecture,
        "layer": layer,
        "component": component,
        "stage": stage,
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
            correlation_id=exc.correlation_id,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            upstream = detail.get("response")
            if isinstance(upstream, dict):
                candidate = str(
                    upstream.get("code") or upstream.get("error_code") or ""
                )
                public_code = (
                    candidate
                    if candidate in CATALOG
                    else _public_code_for_status(exc.status_code)
                )
                entry = CATALOG[public_code]
                return _problem_response(
                    request,
                    public_code=public_code,
                    status_code=entry.http_status,
                    message=entry.message,
                    context=_safe_upstream_context(detail, upstream),
                    headers=exc.headers,
                    correlation_id=(
                        _safe_correlation_id(upstream.get("correlation_id"))
                        or correlation_id_for_request(request)
                    ),
                )
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
        resolved_public_code = public_code or _public_code_for_status(exc.status_code)
        if exc.status_code >= 500:
            correlation_id = correlation_id_for_request(request)
            entry = CATALOG[resolved_public_code]
            logger.warning(
                "Sanitized untyped HTTP failure correlation_id=%s path=%s status=%s code=%s",
                correlation_id,
                request.url.path,
                exc.status_code,
                resolved_public_code,
            )
            return _problem_response(
                request,
                public_code=resolved_public_code,
                status_code=entry.http_status,
                message=entry.message,
                context={
                    "architecture": "SOA",
                    "layer": "oqlos",
                    "component": "oqlos-api",
                    "stage": "http.exception",
                    "problem_source": "api-boundary",
                },
                diagnostics=diagnostics,
                headers=exc.headers,
                correlation_id=correlation_id,
            )
        return _problem_response(
            request,
            public_code=resolved_public_code,
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
        correlation_id = correlation_id_for_request(request)
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
