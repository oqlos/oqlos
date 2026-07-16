"""Unit tests for log file listing and tail reads."""

from __future__ import annotations

from pathlib import Path

import pytest

from oqlos.hardware import log_files as logs


def test_list_log_files_groups_by_day(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OQLOS_LOG_DIR", str(tmp_path))
    (tmp_path / "oqlos-hardware-api.log").write_text("line\n", encoding="utf-8")
    (tmp_path / "evil.log").write_text("ok\n", encoding="utf-8")
    (tmp_path / "not-a-log.txt").write_text("skip\n", encoding="utf-8")

    payload = logs.list_log_files()
    assert payload["ok"] is True
    names = [row["name"] for group in payload["groups"] for row in group["files"]]
    assert "oqlos-hardware-api.log" in names
    assert "evil.log" in names
    assert "not-a-log.txt" not in names
    assert payload["groups"][0]["day"]


def test_read_log_rejects_traversal(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OQLOS_LOG_DIR", str(tmp_path))
    result = logs.read_log("file:../secrets.log")
    assert result["ok"] is False


def test_read_log_tails_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OQLOS_LOG_DIR", str(tmp_path))
    path = tmp_path / "service.log"
    path.write_text("\n".join(f"line-{index}" for index in range(20)), encoding="utf-8")

    result = logs.read_log("file:service.log", lines=5)
    assert result["ok"] is True
    assert "line-19" in result["text"]
    assert "line-0" not in result["text"]


def test_read_log_missing_dir(monkeypatch) -> None:
    monkeypatch.setenv("OQLOS_LOG_DIR", "/tmp/does-not-exist-oqlos-logs")
    payload = logs.list_log_files()
    assert payload["ok"] is True
    assert payload["groups"] == []
    assert len(payload["journal_units"]) >= 1


def test_resolve_log_dir_uses_redeploy_logs_when_default_missing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OQLOS_LOG_DIR", raising=False)
    monkeypatch.delenv("MASKSERVICE_LOG_DIR", raising=False)
    redeploy = tmp_path / ".redeploy" / "logs"
    redeploy.mkdir(parents=True)
    (redeploy / "dev.log").write_text("line\n", encoding="utf-8")
    monkeypatch.setattr(logs, "_REDEPLOY_LOGS_DIR", redeploy)
    monkeypatch.setattr(logs, "_DEFAULT_LOG_DIR", str(tmp_path / "missing" / "logs"))

    assert logs.resolve_log_dir() == redeploy
    payload = logs.list_log_files()
    names = [row["name"] for group in payload["groups"] for row in group["files"]]
    assert "dev.log" in names
