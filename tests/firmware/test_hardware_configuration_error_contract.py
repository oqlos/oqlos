"""Safe problem-details contracts for hardware configuration routes."""

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from oqlos.api import hardware_configuration_routes as routes
from oqlos.api.main import app
from oqlos.hardware.configuration import HardwareConfigurationError


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _assert_problem(
    response,
    *,
    status: int,
    code: str,
    issue_code: str | None,
    stage: str,
    correlation_id: str,
) -> dict:
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == code
    assert body["correlation_id"] == correlation_id
    expected_component = "hardware-configuration" if issue_code else "oqlos-api"
    assert body["component"] == expected_component
    assert body["stage"] == stage
    if issue_code is not None:
        assert body["metadata"]["diagnostics"]["issue_code"] == issue_code
    assert "hunter2" not in response.text
    assert "filesystem root" not in response.text
    return body


def test_missing_active_configuration_is_safe_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing() -> Path:
        raise FileNotFoundError("password=hunter2 filesystem root")

    monkeypatch.setattr(routes, "resolve_oqlos_config_path", _missing)

    response = _client().get(
        "/api/v3/hardware/configuration",
        headers={"X-Correlation-ID": "cor-config-missing"},
    )

    body = _assert_problem(
        response,
        status=503,
        code="C2004-HW-0012",
        issue_code="config_unavailable",
        stage="config.resolve",
        correlation_id="cor-config-missing",
    )
    assert body["metadata"]["context"]["operation_id"] == (
        "hardware.configuration.get"
    )


def test_invalid_configuration_is_safe_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _invalid(*_args, **_kwargs):
        raise HardwareConfigurationError(
            "password=hunter2 invalid configuration",
            format="json",
            source="/filesystem/root/password=hunter2.json",
            issues=[
                {
                    "field": "password=hunter2",
                    "message": "secret value invalid",
                    "type": "value_error",
                }
            ],
        )

    monkeypatch.setattr(routes, "parse_hardware_configuration", _invalid)

    response = _client().post(
        "/api/v3/hardware/configuration/validate",
        json={"content": "password=hunter2", "format": "json"},
        headers={"X-Correlation-ID": "cor-config-invalid"},
    )

    body = _assert_problem(
        response,
        status=422,
        code="C2004-DATA-0002",
        issue_code="api_hardware_configuration_invalid",
        stage="config.validate",
        correlation_id="cor-config-invalid",
    )
    context = body["metadata"]["context"]
    assert context["operation_id"] == "hardware.configuration.validate"
    assert context["reason"] == "configuration_invalid"
    assert context["format"] == "json"
    assert context["issue_count"] == 1
    assert "source" not in context
    assert "issues" not in context


def test_configuration_read_io_failure_is_safe_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "oqlos.json"
    target.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(routes, "_configured_path", lambda _operation_id: target)

    def _unavailable(*_args, **_kwargs):
        try:
            raise OSError("password=hunter2 filesystem root")
        except OSError as cause:
            raise HardwareConfigurationError(
                "password=hunter2 read failed",
                source="/filesystem/root/oqlos.json",
            ) from cause

    monkeypatch.setattr(routes, "load_hardware_configuration", _unavailable)

    response = _client().get(
        "/api/v3/hardware/configuration",
        headers={"X-Correlation-ID": "cor-config-read"},
    )

    body = _assert_problem(
        response,
        status=503,
        code="C2004-HW-0012",
        issue_code="config_unavailable",
        stage="config.load",
        correlation_id="cor-config-read",
    )
    assert body["metadata"]["context"]["operation_id"] == (
        "hardware.configuration.get"
    )


def test_malformed_active_configuration_is_safe_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "oqlos.json"
    target.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(routes, "_configured_path", lambda _operation_id: target)

    def _malformed(*_args, **_kwargs):
        raise HardwareConfigurationError(
            "password=hunter2 malformed configuration",
            format="json",
            source="/filesystem/root/oqlos.json",
        )

    monkeypatch.setattr(routes, "load_hardware_configuration", _malformed)

    response = _client().get(
        "/api/v3/hardware/configuration",
        headers={"X-Correlation-ID": "cor-config-malformed"},
    )

    body = _assert_problem(
        response,
        status=503,
        code="C2004-HW-0012",
        issue_code="config_unavailable",
        stage="config.load",
        correlation_id="cor-config-malformed",
    )
    assert body["metadata"]["context"]["operation_id"] == (
        "hardware.configuration.get"
    )


@pytest.mark.parametrize(
    ("file_name", "format", "reason"),
    [
        ("../password=hunter2.json", "json", "file_name_invalid"),
        ("oqlos.yaml", "json", "format_mismatch"),
    ],
)
def test_save_target_validation_is_safe_data_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    file_name: str,
    format: str,
    reason: str,
) -> None:
    current = tmp_path / "oqlos.json"
    monkeypatch.setattr(routes, "_configured_path", lambda _operation_id: current)

    response = _client().put(
        "/api/v3/hardware/configuration/source",
        json={"content": "{}", "format": format, "file_name": file_name},
        headers={
            "X-Connect-Role": "system",
            "X-Correlation-ID": "cor-config-target",
        },
    )

    body = _assert_problem(
        response,
        status=422,
        code="C2004-DATA-0002",
        issue_code="api_hardware_configuration_invalid",
        stage="target.validate",
        correlation_id="cor-config-target",
    )
    context = body["metadata"]["context"]
    assert context["operation_id"] == "hardware.configuration.save"
    assert context["reason"] == reason


def test_configuration_write_io_failure_is_safe_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = tmp_path / "oqlos.json"
    monkeypatch.setattr(routes, "_configured_path", lambda _operation_id: current)
    monkeypatch.setattr(
        routes,
        "parse_hardware_configuration",
        lambda *_args, **_kwargs: SimpleNamespace(schema_version="test"),
    )

    def _write_failure(*_args, **_kwargs):
        raise OSError("password=hunter2 filesystem root")

    monkeypatch.setattr(routes, "save_hardware_configuration", _write_failure)

    response = _client().put(
        "/api/v3/hardware/configuration/source",
        json={"content": "{}", "format": "json", "file_name": "oqlos.json"},
        headers={
            "X-Connect-Role": "system",
            "X-Correlation-ID": "cor-config-write",
        },
    )

    body = _assert_problem(
        response,
        status=503,
        code="C2004-HW-0012",
        issue_code="config_unavailable",
        stage="config.persist",
        correlation_id="cor-config-write",
    )
    assert body["metadata"]["context"]["operation_id"] == (
        "hardware.configuration.save"
    )


def test_invalid_file_listing_does_not_publish_parser_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = tmp_path / "oqlos.json"
    current.write_text("password=hunter2", encoding="utf-8")
    monkeypatch.setattr(routes, "_configured_path", lambda _operation_id: current)

    def _invalid_file(*_args, **_kwargs):
        raise HardwareConfigurationError(
            "password=hunter2 invalid file",
            source="/filesystem/root/oqlos.json",
        )

    monkeypatch.setattr(routes, "load_hardware_configuration", _invalid_file)

    response = _client().get("/api/v3/hardware/configuration/files")

    assert response.status_code == 200
    item = response.json()["files"][0]
    assert item["valid"] is False
    assert item["error"] == "Invalid hardware configuration"
    assert item["error_code"] == "C2004-DATA-0002"
    assert item["issue_code"] == "api_hardware_configuration_invalid"
    assert "hunter2" not in response.text
    assert "filesystem root" not in response.text


def test_unexpected_configuration_failure_uses_sanitized_api_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected() -> Path:
        raise RuntimeError("password=hunter2 filesystem root")

    monkeypatch.setattr(routes, "resolve_oqlos_config_path", _unexpected)

    response = _client().get(
        "/api/v3/hardware/configuration",
        headers={"X-Correlation-ID": "cor-config-unexpected"},
    )

    _assert_problem(
        response,
        status=500,
        code="C2004-SYS-0000",
        issue_code=None,
        stage="api.error",
        correlation_id="cor-config-unexpected",
    )
