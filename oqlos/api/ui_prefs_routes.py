"""OqlOS UI chrome preferences API."""

from __future__ import annotations

from typing import Any, NoReturn

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from oqlos.api.ui_prefs_store import UI_PREFS_STORE_ERRORS, ui_prefs_store
from oqlos.errors import OqlosError

router = APIRouter(prefix="/api/v3/ui", tags=["ui-prefs"])


class UiPrefsReplaceRequest(BaseModel):
    prefs: dict[str, Any] = Field(default_factory=dict)
    persist: bool = True
    merge: bool = True


def _raise_ui_prefs_store_unavailable(
    *,
    stage: str,
    operation_id: str,
    cause: Exception,
) -> NoReturn:
    raise OqlosError(
        code="api_ui_prefs_store_unavailable",
        status_code=503,
        detail={
            "architecture": "SOA",
            "layer": "oqlos",
            "component": "ui-prefs-store",
            "stage": stage,
            "problem_source": "storage",
            "operation_id": operation_id,
            "upstream_target": "file-store://ui-preferences",
        },
    ) from cause


@router.get("/prefs")
async def get_ui_prefs() -> dict[str, Any]:
    try:
        prefs = ui_prefs_store.get()
    except UI_PREFS_STORE_ERRORS as exc:
        _raise_ui_prefs_store_unavailable(
            stage="preferences.load",
            operation_id="ui.preferences.read",
            cause=exc,
        )
    return {
        "ok": True,
        "prefs": prefs,
    }


@router.put("/prefs")
async def put_ui_prefs(req: UiPrefsReplaceRequest = Body()) -> dict[str, Any]:
    try:
        if req.merge:
            prefs = ui_prefs_store.merge(req.prefs, persist=req.persist)
        else:
            prefs = ui_prefs_store.replace(req.prefs, persist=req.persist)
    except UI_PREFS_STORE_ERRORS as exc:
        _raise_ui_prefs_store_unavailable(
            stage="preferences.persist" if req.persist else "preferences.update",
            operation_id="ui.preferences.write",
            cause=exc,
        )
    return {
        "ok": True,
        "prefs": prefs,
    }
