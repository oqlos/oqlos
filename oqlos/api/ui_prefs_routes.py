"""OqlOS UI chrome preferences API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from oqlos.api.ui_prefs_store import ui_prefs_store

router = APIRouter(prefix="/api/v3/ui", tags=["ui-prefs"])


class UiPrefsReplaceRequest(BaseModel):
    prefs: dict[str, Any] = Field(default_factory=dict)
    persist: bool = True
    merge: bool = True


@router.get("/prefs")
async def get_ui_prefs() -> dict[str, Any]:
    return {
        "ok": True,
        "prefs": ui_prefs_store.get(),
        "store_path": ui_prefs_store.file_path,
    }


@router.put("/prefs")
async def put_ui_prefs(req: UiPrefsReplaceRequest = Body()) -> dict[str, Any]:
    if req.merge:
        prefs = ui_prefs_store.merge(req.prefs, persist=req.persist)
    else:
        prefs = ui_prefs_store.replace(req.prefs, persist=req.persist)
    return {
        "ok": True,
        "prefs": prefs,
        "store_path": ui_prefs_store.file_path,
    }
