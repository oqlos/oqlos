"""Persistent OqlOS UI chrome prefs (sidebar collapse, panel pins)."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from oqlos.shared.file_ops import env_configured_path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def _default_path() -> Path:
    return env_configured_path(
        ("OQLOS_UI_PREFS_FILE", "UI_PREFS_FILE"),
        Path.home() / "oqlos" / "ui-prefs.yaml",
    )


def empty_prefs() -> dict[str, str]:
    return {}


def normalize_prefs(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, str] = {}
    for key, raw in value.items():
        token = str(key or "").strip()
        if not token:
            continue
        out[token] = str(raw)
    return out


class UiPrefsStoreUnavailableError(Exception):
    """Raised when the configured preferences format cannot be processed."""


UI_PREFS_STORE_ERRORS = (
    OSError,
    UnicodeError,
    json.JSONDecodeError,
    UiPrefsStoreUnavailableError,
    *((yaml.YAMLError,) if yaml is not None else ()),
)


class UiPrefsStore:
    def __init__(self, file_path: str | Path | None = None) -> None:
        self._path = Path(file_path).expanduser() if file_path else _default_path()
        self._prefs = empty_prefs()

    @property
    def file_path(self) -> str:
        return str(self._path)

    def _load_from_disk(self) -> None:
        if not self._path.exists():
            self._prefs = empty_prefs()
            return
        raw = self._path.read_text(encoding="utf-8")
        if self._path.suffix.lower() == ".json":
            payload = json.loads(raw or "{}")
        else:
            if yaml is None:
                raise UiPrefsStoreUnavailableError(
                    "PyYAML is required to read YAML ui prefs"
                )
            payload = yaml.safe_load(raw) if raw.strip() else {}
        self._prefs = normalize_prefs(
            payload.get("prefs") if isinstance(payload, dict) else payload
        )

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"prefs": self._prefs}
        if self._path.suffix.lower() == ".json":
            text = json.dumps(payload, ensure_ascii=False, indent=2)
        else:
            if yaml is None:
                raise UiPrefsStoreUnavailableError(
                    "PyYAML is required to persist YAML ui prefs"
                )
            text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        self._path.write_text(text, encoding="utf-8")

    def get(self) -> dict[str, str]:
        self._load_from_disk()
        return deepcopy(self._prefs)

    def merge(self, patch: dict[str, Any], *, persist: bool = True) -> dict[str, str]:
        self._load_from_disk()
        normalized = normalize_prefs(patch)
        self._prefs.update(normalized)
        if persist:
            self.save()
        return deepcopy(self._prefs)

    def replace(self, prefs: dict[str, Any], *, persist: bool = True) -> dict[str, str]:
        self._prefs = normalize_prefs(prefs)
        if persist:
            self.save()
        return deepcopy(self._prefs)


ui_prefs_store = UiPrefsStore()
