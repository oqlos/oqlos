"""Database-backed OqlOS preferences (including panel scenario drafts)."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3
from typing import Any

from oqlos.shared.file_ops import env_configured_path


class UiPrefsStoreUnavailableError(Exception):
    """Preferences could not be read or committed."""


UI_PREFS_STORE_ERRORS = (OSError, UnicodeError, json.JSONDecodeError, sqlite3.Error,
                         UiPrefsStoreUnavailableError)


def empty_prefs() -> dict[str, str]:
    return {}


def normalize_prefs(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key).strip(): str(raw) for key, raw in value.items() if str(key or '').strip()}


class UiPrefsStore:
    def __init__(self, file_path: str | Path | None = None) -> None:
        legacy = Path(file_path).expanduser() if file_path else env_configured_path(
            ('OQLOS_UI_PREFS_FILE', 'UI_PREFS_FILE'), Path.home() / 'oqlos' / 'ui-prefs.yaml')
        self._legacy = legacy if legacy.suffix in ('.json', '.yaml', '.yml') else None
        self._path = legacy.with_suffix('.sqlite3') if self._legacy else legacy
        if file_path is None:
            self._path = env_configured_path(('OQLOS_UI_PREFS_DB',), self._path)

    @property
    def file_path(self) -> str:
        return str(self._path)

    def _connect(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self._path, timeout=10)
        try:
            with db:
                db.execute('CREATE TABLE IF NOT EXISTS ui_preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                db.execute('CREATE TABLE IF NOT EXISTS ui_preferences_meta (key TEXT PRIMARY KEY)')
                if not db.execute("SELECT key FROM ui_preferences_meta WHERE key='legacy-imported'").fetchone():
                    if self._legacy and self._legacy.exists():
                        raw = self._legacy.read_text(encoding='utf-8')
                        if self._legacy.suffix == '.json':
                            payload = json.loads(raw)
                        else:
                            import yaml
                            try:
                                payload = yaml.safe_load(raw)
                            except yaml.YAMLError as exc:
                                raise UiPrefsStoreUnavailableError('Invalid legacy preferences') from exc
                        prefs = normalize_prefs(payload.get('prefs', {}) if isinstance(payload, dict) else {})
                        db.executemany('INSERT OR IGNORE INTO ui_preferences VALUES (?, ?)', prefs.items())
                    db.execute("INSERT INTO ui_preferences_meta VALUES ('legacy-imported')")
        except Exception:
            db.close()
            raise

        return db

    def get(self) -> dict[str, str]:
        db = self._connect()
        try:
            return dict(db.execute('SELECT key, value FROM ui_preferences'))
        finally:
            db.close()

    def _write(self, prefs: dict[str, Any], replace: bool, persist: bool):
        normalized = normalize_prefs(prefs)
        db = self._connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            if replace:
                db.execute('DELETE FROM ui_preferences')
            db.executemany('INSERT INTO ui_preferences(key, value) VALUES (?, ?) '
                           'ON CONFLICT(key) DO UPDATE SET value=excluded.value', normalized.items())
            result = dict(db.execute('SELECT key, value FROM ui_preferences'))
            if persist:
                db.commit()
            else:
                db.rollback()
            return deepcopy(result)
        finally:
            db.close()

    def merge(self, patch: dict[str, Any], *, persist: bool = True) -> dict[str, str]:
        return self._write(patch, False, persist)

    def replace(self, prefs: dict[str, Any], *, persist: bool = True) -> dict[str, str]:
        return self._write(prefs, True, persist)


ui_prefs_store = UiPrefsStore()
