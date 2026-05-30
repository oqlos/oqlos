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
