"""List and tail log files under the OqlOS log directory."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG_NAME_RE = re.compile(r"^[\w.-]+\.log(\.\d+)?$")
_MAX_READ_BYTES = 512 * 1024
_MAX_LINES = 500
_DEFAULT_LOG_DIR = "~/maskservice/logs"
_REDEPLOY_LOGS_DIR = Path(__file__).resolve().parents[2] / ".redeploy" / "logs"


def resolve_log_dir() -> Path:
    raw = (os.getenv("OQLOS_LOG_DIR") or os.getenv("MASKSERVICE_LOG_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    try:
        from oqlos.config import get_settings

        log_file = str(get_settings().log_file or "").strip()
        if log_file:
            parent = Path(log_file).expanduser().parent
            if parent.is_dir():
                return parent
    except Exception:
        pass
    default = Path(_DEFAULT_LOG_DIR).expanduser()
    if default.is_dir():
        return default
    if _REDEPLOY_LOGS_DIR.is_dir():
        return _REDEPLOY_LOGS_DIR
    return default


def _is_safe_name(name: str) -> bool:
    base = Path(name).name
    if base != name or not base:
        return False
    return bool(_LOG_NAME_RE.match(base))


def _file_day(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")


def _journal_units_payload() -> list[dict[str, Any]]:
    from oqlos.hardware.systemd_services import service_whitelist

    return [
        {"id": f"journal:{unit}", "name": unit, "kind": "journal"}
        for unit in service_whitelist()
    ]


def list_log_files() -> dict[str, Any]:
    log_dir = resolve_log_dir()
    journal_units = _journal_units_payload()
    if not log_dir.is_dir():
        return {
            "ok": True,
            "dir": str(log_dir),
            "groups": [],
            "journal_units": journal_units,
            "empty_reason": "log directory missing",
        }

    files: list[dict[str, Any]] = []
    for entry in log_dir.iterdir():
        if not entry.is_file() or not _is_safe_name(entry.name):
            continue
        stat = entry.stat()
        files.append(
            {
                "id": f"file:{entry.name}",
                "name": entry.name,
                "kind": "file",
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "day": _file_day(stat.st_mtime),
            }
        )
    files.sort(key=lambda row: row["modified"], reverse=True)

    groups_map: dict[str, list[dict[str, Any]]] = {}
    for row in files:
        groups_map.setdefault(row["day"], []).append(row)
    groups = [{"day": day, "files": groups_map[day]} for day in sorted(groups_map, reverse=True)]

    return {
        "ok": True,
        "dir": str(log_dir),
        "groups": groups,
        "journal_units": journal_units,
    }


def _tail_text(path: Path, lines: int) -> str:
    count = max(1, min(int(lines), _MAX_LINES))
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        if size == 0:
            return ""
        block = min(size, _MAX_READ_BYTES)
        handle.seek(-block, os.SEEK_END)
        data = handle.read().decode("utf-8", errors="replace")
    return "\n".join(data.splitlines()[-count:])


def read_log(log_id: str, lines: int = 200) -> dict[str, Any]:
    token = str(log_id or "").strip()
    if not token:
        return {"ok": False, "error": "log id required"}

    if token.startswith("journal:"):
        from oqlos.hardware.systemd_services import service_logs

        unit = token.split(":", 1)[1]
        result = service_logs(unit, lines=lines)
        if not result.get("ok"):
            return result
        return {
            "ok": True,
            "id": token,
            "kind": "journal",
            "name": result.get("unit", unit),
            "lines": result.get("lines", lines),
            "text": result.get("log", ""),
        }

    name = token.split(":", 1)[1] if token.startswith("file:") else token
    if not _is_safe_name(name):
        return {"ok": False, "error": "invalid log file name"}

    path = resolve_log_dir() / name
    if not path.is_file():
        return {"ok": False, "error": f"log file not found: {name}"}
    try:
        text = _tail_text(path, lines)
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "id": f"file:{name}",
        "kind": "file",
        "name": name,
        "lines": max(1, min(int(lines), _MAX_LINES)),
        "text": text,
    }


__all__ = ["list_log_files", "read_log", "resolve_log_dir"]
