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
