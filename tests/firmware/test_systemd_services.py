"""Unit tests for the whitelisted systemd service control module."""

from __future__ import annotations

import subprocess

import pytest

from oqlos.hardware import systemd_services as svc


def test_normalize_unit_appends_service_suffix():
    assert svc.normalize_unit("mosquitto") == "mosquitto.service"
    assert svc.normalize_unit("oqlos-hardware-api.service") == "oqlos-hardware-api.service"
    assert svc.normalize_unit("foo.socket") == "foo.socket"
    assert svc.normalize_unit("  kiosk  ") == "kiosk.service"


def test_whitelist_env_override(monkeypatch):
    monkeypatch.setenv("OQLOS_SYSTEMD_WHITELIST", "alpha, beta.service ,")
    assert svc.service_whitelist() == ["alpha.service", "beta.service"]
    assert svc.is_whitelisted("alpha")
    assert not svc.is_whitelisted("mosquitto")


def test_default_whitelist_contains_core_units(monkeypatch):
    monkeypatch.delenv("OQLOS_SYSTEMD_WHITELIST", raising=False)
    wl = svc.service_whitelist()
    assert "oqlos-hardware-api.service" in wl
    assert "mosquitto.service" in wl


def test_control_rejects_unknown_action():
    result = svc.control_service("mosquitto", "frobnicate")
    assert result["ok"] is False
    assert "Unsupported action" in result["error"]


def test_control_rejects_non_whitelisted(monkeypatch):
    monkeypatch.delenv("OQLOS_SYSTEMD_WHITELIST", raising=False)
    result = svc.control_service("sshd", "restart")
    assert result["ok"] is False
    assert "whitelist" in result["error"].lower()


def test_control_status_uses_show_not_sudo(monkeypatch):
    monkeypatch.setattr(svc, "_systemctl_available", lambda: True)
    monkeypatch.setattr(
        svc,
        "_service_status",
        lambda unit: {"unit": unit, "available": True, "running": True},
    )

    def _fail_run(*_args, **_kwargs):  # sudo must not be invoked for status
        raise AssertionError("subprocess.run should not be called for status")

    monkeypatch.setattr(subprocess, "run", _fail_run)
    result = svc.control_service("mosquitto", "status")
    assert result["ok"] is True
    assert result["status"]["running"] is True


def test_control_start_requires_sudo_in_system_scope(monkeypatch):
    monkeypatch.setenv("OQLOS_SYSTEMD_SCOPE", "system")
    monkeypatch.setattr(svc, "_systemctl_available", lambda: True)
    monkeypatch.setattr(svc, "_sudo_available", lambda: False)
    result = svc.control_service("mosquitto", "restart")
    assert result["ok"] is False
    assert "sudo" in result["error"].lower()


def test_control_start_invokes_user_systemctl_by_default(monkeypatch):
    monkeypatch.delenv("OQLOS_SYSTEMD_SCOPE", raising=False)
    monkeypatch.setattr(svc, "_systemctl_available", lambda: True)
    monkeypatch.setattr(svc, "_sudo_available", lambda: True)
    monkeypatch.setattr(svc, "_service_status", lambda unit: {"unit": unit, "running": True})
    calls: list[list[str]] = []

    def _fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = svc.control_service("mosquitto", "restart")
    assert result["ok"] is True
    assert calls == [["systemctl", "--user", "restart", "mosquitto.service"]]


def test_control_start_invokes_sudo_systemctl_in_system_scope(monkeypatch):
    monkeypatch.setenv("OQLOS_SYSTEMD_SCOPE", "system")
    monkeypatch.setattr(svc, "_systemctl_available", lambda: True)
    monkeypatch.setattr(svc, "_sudo_available", lambda: True)
    monkeypatch.setattr(svc, "_service_status", lambda unit: {"unit": unit, "running": True})
    calls: list[list[str]] = []

    def _fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = svc.control_service("mosquitto", "restart")
    assert result["ok"] is True
    assert calls == [["sudo", "-n", "systemctl", "restart", "mosquitto.service"]]


def test_list_services_without_systemctl(monkeypatch):
    monkeypatch.setattr(svc, "_systemctl_available", lambda: False)
    result = svc.list_services()
    assert result["ok"] is False
    assert result["services"] == []


def test_service_logs_rejects_non_whitelisted():
    result = svc.service_logs("sshd", lines=10)
    assert result["ok"] is False


def test_parse_show_extracts_properties():
    out = "Id=mosquitto.service\nActiveState=active\nSubState=running\nMainPID=1234\n"
    props = svc._parse_show(out)
    assert props["ActiveState"] == "active"
    assert props["MainPID"] == "1234"
