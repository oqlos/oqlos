"""Tests for OqlOS logging configuration."""

from __future__ import annotations

import logging

from oqlos.shared.logger import configure_oqlos_logging


def test_configure_oqlos_logging_writes_to_file(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "oqlos-test.log"
    monkeypatch.setenv("OQLOS_LOG_FILE", str(log_path))
    monkeypatch.setenv("OQLOS_LOG_LEVEL", "INFO")

    configure_oqlos_logging(force=True)
    logging.getLogger("oqlos.test").info("hardware init probe line")

    assert log_path.is_file()
    content = log_path.read_text(encoding="utf-8")
    assert "hardware init probe line" in content


def test_configure_oqlos_logging_suppresses_http_client_info(monkeypatch) -> None:
    monkeypatch.delenv("OQLOS_HTTP_CLIENT_LOG_LEVEL", raising=False)

    configure_oqlos_logging(force=True)

    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


def test_configure_oqlos_logging_accepts_bounded_rotation_settings(
    tmp_path, monkeypatch
) -> None:
    log_path = tmp_path / "oqlos-test.log"
    monkeypatch.setenv("OQLOS_LOG_FILE", str(log_path))
    monkeypatch.setenv("OQLOS_LOG_MAX_BYTES", "123456")
    monkeypatch.setenv("OQLOS_LOG_BACKUP_COUNT", "7")
    monkeypatch.setenv("OQLOS_HTTP_CLIENT_LOG_LEVEL", "DEBUG")

    configure_oqlos_logging(force=True)

    rotating = next(
        handler
        for handler in logging.getLogger().handlers
        if hasattr(handler, "maxBytes")
    )
    assert rotating.maxBytes == 123456
    assert rotating.backupCount == 7
    assert logging.getLogger("httpx").level == logging.DEBUG
