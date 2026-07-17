"""Collect deploy/update status for OqlOS / BoardNet."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from oqlos.config import FIRMWARE_PORT, SERVICE_NAME, SERVICE_VERSION


def repo_root() -> Path:
    env = os.environ.get("OQLOS_REPO_ROOT", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def logs_dir() -> Path:
    env = os.environ.get("OQLOS_LOGS_DIR", "").strip()
    if env:
        return Path(env)
    return repo_root() / "logs"


def _read_text_file(path: Path) -> str | None:
    try:
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            return text or None
    except OSError:
        pass
    return None


def read_deploy_commit() -> dict[str, Any]:
    candidates: list[Path] = []
    env_path = os.environ.get("OQLOS_DEPLOY_COMMIT_FILE", "").strip()
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend([repo_root() / ".deploy-commit", logs_dir() / ".deploy-commit"])
    for path in candidates:
        commit = _read_text_file(path)
        if commit:
            return {"commit": commit, "short": commit[:12], "source": str(path)}
    return {"commit": None, "short": None, "source": None}


def read_update_progress() -> dict[str, Any]:
    env_path = os.environ.get("OQLOS_UPDATE_STATUS_FILE", "").strip()
    path = Path(env_path) if env_path else logs_dir() / "update-status.json"
    try:
        if not path.is_file():
            return {"active": False, "source": str(path)}
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"active": False, "source": str(path), "error": "invalid-json"}
        active = bool(data.get("active")) and not data.get("done")
        return {"active": active, "source": str(path), **{k: data.get(k) for k in (
            "action", "phase", "sub", "step", "total", "version", "ts", "done"
        )}}
    except (OSError, json.JSONDecodeError) as exc:
        return {"active": False, "source": str(path), "error": str(exc)}


def compute_git_drift(deploy_commit: str | None, *, root: Path | None = None) -> dict[str, Any]:
    project_root = root or repo_root()
    if not deploy_commit:
        return {"status": "no-deploy-commit", "head": None, "commits_behind": None}
    if not (project_root / ".git").is_dir():
        return {"status": "no-git", "head": None, "commits_behind": None}
    try:
        head = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        if head == deploy_commit:
            dirty = subprocess.run(
                ["git", "-C", str(project_root), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            ).stdout.strip()
            return {
                "status": "current" if not dirty else "current+wip",
                "head": head,
                "short_head": head[:12],
                "commits_behind": 0,
            }
        count_raw = subprocess.run(
            ["git", "-C", str(project_root), "rev-list", "--count", f"{deploy_commit}..HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        return {
            "status": "behind",
            "head": head,
            "short_head": head[:12],
            "commits_behind": int(count_raw) if count_raw.isdigit() else None,
        }
    except (subprocess.SubprocessError, ValueError, OSError):
        return {"status": "error", "head": None, "commits_behind": None}


def build_update_status_payload(
    *,
    deploy: dict[str, Any],
    update_progress: dict[str, Any],
    git_drift: dict[str, Any],
    health: dict[str, Any],
    hardware: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deploy_active = bool(update_progress.get("active"))
    return {
        "status": "updating" if deploy_active else "ok",
        "host": "boardnet",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "port": FIRMWARE_PORT,
        "deploy": deploy,
        "update_progress": update_progress,
        "deploy_in_progress": deploy_active,
        "git_drift": git_drift,
        "health": health,
        "hardware": hardware or {},
    }
