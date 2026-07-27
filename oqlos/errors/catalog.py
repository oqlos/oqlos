"""OqlIssue catalog: single source of truth for every OqlOS diagnostic code.

Each entry documents one ``code`` string used with
``oqlos.tools.hardware_diagnose.doctor_common.add_issue`` (and, going forward,
by the runtime diagnosis/API/frontend layers). ``docs/ERROR_CODES.md`` is
generated from this module by ``oqlos/tools/gen_error_docs.py`` — edit the
catalog, not the generated doc.

``actuation_risk`` gates automatic repair:
  - "none": diagnostic only, or requires a host/infra action no automation
    should attempt (e.g. plug in a cable).
  - "config": a plain config/YAML edit with no effect on physical hardware
    until a service restart. Safe for an automated (e.g. LLM-driven) git
    commit.
  - "physical": changes whether/how real hardware is actuated (motors,
    valves). Always requires human confirmation, never auto-committed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

IssueSeverity = Literal["info", "warning", "error", "critical"]
ActuationRisk = Literal["none", "config", "physical"]


@dataclass(frozen=True)
class RepairTemplate:
    id: str
    scope: str = "oqlos"  # oqlos | host
    auto_executable: bool = False
    actuation_risk: ActuationRisk = "none"
    hint: str = ""


@dataclass(frozen=True)
class IssueDefinition:
    code: str
    domain: str  # hardware | api | firmware | scenario | config
    default_severity: IssueSeverity
    summary: str
    repair: RepairTemplate | None = None


_MODBUS_ADAPTER_ONLY_HINT = (
    "USB serial adapter is visible, but the device did not answer. "
    "Check RS485 wiring, power, slave address and baudrate."
)

ISSUE_CATALOG: dict[str, IssueDefinition] = {
    "modbus_adc_adapter_only": IssueDefinition(
        code="modbus_adc_adapter_only",
        domain="hardware",
        default_severity="warning",
        summary=_MODBUS_ADAPTER_ONLY_HINT,
    ),
    "modbus_adc_not_detected": IssueDefinition(
        code="modbus_adc_not_detected",
        domain="hardware",
        default_severity="warning",
        summary="Modbus ADC device was not detected on any probed serial port.",
    ),
    "modbus_adc_config_missing": IssueDefinition(
        code="modbus_adc_config_missing",
        domain="config",
        default_severity="warning",
        summary="oqlos.yaml does not define the modbus-adc plugin.",
    ),
    "modbus_adc_disabled_but_present": IssueDefinition(
        code="modbus_adc_disabled_but_present",
        domain="config",
        default_severity="warning",
        summary=(
            "Modbus ADC device responds on the serial bus, but modbus-adc is "
            "disabled in oqlos.yaml."
        ),
        repair=RepairTemplate(
            id="enable_modbus_adc_config",
            scope="host",
            auto_executable=True,
            actuation_risk="config",
            hint="Set plugins.modbus-adc.enabled: true and correct serial_port in oqlos.yaml, then restart the service.",
        ),
    ),
    "modbus_adc_config_mismatch": IssueDefinition(
        code="modbus_adc_config_mismatch",
        domain="config",
        default_severity="error",
        summary="oqlos.yaml Modbus ADC settings do not match the responding device.",
        repair=RepairTemplate(
            id="update_modbus_adc_config",
            scope="host",
            auto_executable=True,
            actuation_risk="config",
            hint="Update plugins.modbus-adc.connection_params in oqlos.yaml to match the detected device, then restart the service.",
        ),
    ),
    "modbus_adapter_only": IssueDefinition(
        code="modbus_adapter_only",
        domain="hardware",
        default_severity="warning",
        summary=_MODBUS_ADAPTER_ONLY_HINT,
    ),
    "modbus_not_detected": IssueDefinition(
        code="modbus_not_detected",
        domain="hardware",
        default_severity="error",
        summary="Modbus RTU (modbus-io) device was not detected on any probed serial port.",
    ),
    "config_unavailable": IssueDefinition(
        code="config_unavailable",
        domain="config",
        default_severity="error",
        summary="oqlos.yaml could not be loaded.",
    ),
    "modbus_config_missing": IssueDefinition(
        code="modbus_config_missing",
        domain="config",
        default_severity="error",
        summary="oqlos.yaml does not define the modbus-io plugin.",
    ),
    "modbus_config_mismatch": IssueDefinition(
        code="modbus_config_mismatch",
        domain="config",
        default_severity="error",
        summary="oqlos.yaml Modbus (modbus-io) settings do not match the responding device.",
        repair=RepairTemplate(
            id="update_modbus_config",
            scope="host",
            auto_executable=True,
            actuation_risk="config",
            hint="Update plugins.modbus-io.connection_params in oqlos.yaml to match the detected device, then restart the service.",
        ),
    ),
    "modbus_preflight_exception": IssueDefinition(
        code="modbus_preflight_exception",
        domain="hardware",
        default_severity="error",
        summary="The Modbus topology preflight failed before a valid report could be produced.",
    ),
    "pimodbus_unavailable": IssueDefinition(
        code="pimodbus_unavailable",
        domain="config",
        default_severity="error",
        summary="The shared pimodbus runtime library is unavailable to OqlOS.",
        repair=RepairTemplate(
            id="install_pimodbus_runtime",
            scope="host",
            auto_executable=False,
            actuation_risk="config",
            hint="Install the pinned pimodbus package into the OqlOS runtime environment and restart OqlOS.",
        ),
    ),
    "serial_port_busy": IssueDefinition(
        code="serial_port_busy",
        domain="hardware",
        default_severity="warning",
        summary="The configured Modbus serial port is already open by another process.",
        repair=RepairTemplate(
            id="release_serial_port",
            scope="host",
            auto_executable=False,
            actuation_risk="none",
            hint="Stop the other process, or point the CLI at that already-running firmware URL instead of probing the same port twice.",
        ),
    ),
    "firmware_unreachable": IssueDefinition(
        code="firmware_unreachable",
        domain="firmware",
        default_severity="error",
        summary="The firmware health endpoint is unavailable.",
        repair=RepairTemplate(
            id="start_firmware",
            scope="host",
            auto_executable=False,
            actuation_risk="none",
            hint="Start oqlos-server or the hardware docker compose stack.",
        ),
    ),
    "firmware_not_real": IssueDefinition(
        code="firmware_not_real",
        domain="firmware",
        default_severity="warning",
        summary="Firmware is running in mock mode; actuator endpoints will not control real hardware.",
        repair=RepairTemplate(
            id="enable_real_mode",
            scope="host",
            auto_executable=False,
            actuation_risk="physical",
            hint="Restart firmware with HARDWARE_MODE=real or OQLOS_HARDWARE_MODE=real. Not auto-applied: it changes runtime actuator behavior.",
        ),
    ),
    "remote_firmware_no_serial_access": IssueDefinition(
        code="remote_firmware_no_serial_access",
        domain="firmware",
        default_severity="warning",
        summary="The CLI host sees USB serial devices, but firmware runs elsewhere and cannot access them.",
        repair=RepairTemplate(
            id="align_firmware_host",
            scope="host",
            auto_executable=False,
            actuation_risk="none",
            hint="Attach the USB/serial hardware to the firmware host, run firmware locally, or point it at network-reachable hardware services.",
        ),
    ),
    "firmware_no_serial_access": IssueDefinition(
        code="firmware_no_serial_access",
        domain="firmware",
        default_severity="warning",
        summary="Host sees USB serial devices, but firmware identify sees none (likely missing device mounts).",
        repair=RepairTemplate(
            id="mount_serial_devices",
            scope="host",
            auto_executable=False,
            actuation_risk="none",
            hint="Mount the detected serial devices into the firmware container, or run firmware on the host; then restart firmware.",
        ),
    ),
    "identify_unavailable": IssueDefinition(
        code="identify_unavailable",
        domain="firmware",
        default_severity="warning",
        summary="The firmware identify endpoint is unavailable.",
    ),
    "hw_tic249_sidecar_unreachable": IssueDefinition(
        code="hw_tic249_sidecar_unreachable",
        domain="hardware",
        default_severity="error",
        summary="hw-tic249 sidecar (:8205, lung motor) is unreachable or not connected to the Pololu Tic USB device.",
        repair=RepairTemplate(
            id="tic249-ensure-sidecar",
            scope="oqlos",
            auto_executable=True,
            actuation_risk="config",
            hint="systemctl --user restart hw-tic249.service, then reconnect the USB handle — no motor motion is issued.",
        ),
    ),
    "hw_dri0050_sidecar_unreachable": IssueDefinition(
        code="hw_dri0050_sidecar_unreachable",
        domain="hardware",
        default_severity="error",
        summary="dri0050-motor-api sidecar (:8203, pump) is unreachable or unhealthy.",
        repair=RepairTemplate(
            id="dri0050-ensure-sidecar",
            scope="oqlos",
            auto_executable=True,
            actuation_risk="config",
            hint="systemd-run the dri0050-motor-api sidecar (same as make hardware-up), without restarting the full stack.",
        ),
    ),
    "hw_modbus_serial_handle_stale": IssueDefinition(
        code="hw_modbus_serial_handle_stale",
        domain="hardware",
        default_severity="warning",
        summary="A Modbus RTU plugin (modbus-io/modbus-adc) has a stale USB/RS485 serial handle after device re-enumeration (errno 19).",
        repair=RepairTemplate(
            id="modbus-plugin-reconnect",
            scope="oqlos",
            auto_executable=True,
            actuation_risk="none",
            hint="Pure in-process reconnect of the existing plugin instance — no file/config changes, nothing to commit.",
        ),
    ),
    "hw_modbus_no_response": IssueDefinition(
        code="hw_modbus_no_response",
        domain="hardware",
        default_severity="error",
        summary="Modbus RTU slave did not answer (read timed out / no response) on the configured serial path.",
        repair=RepairTemplate(
            id="modbus-physical-check",
            scope="host",
            auto_executable=False,
            actuation_risk="none",
            hint="Verify module power, RS485 A/B polarity, common GND, slave ID (plan: 2) and baud 4800 8N1; software reconnect will not help.",
        ),
    ),
    "api_oql_transport_disabled": IssueDefinition(
        code="api_oql_transport_disabled",
        domain="api",
        default_severity="error",
        summary="OQL-over-MQTT transport is disabled (OQLOS_OQL_TRANSPORT_ROLE=off); /api/v1/oql/execute and /manage cannot run.",
        repair=RepairTemplate(
            id="enable_oql_mqtt_transport",
            scope="host",
            auto_executable=False,
            actuation_risk="config",
            hint="Set OQLOS_OQL_TRANSPORT_ROLE to 'controller'/'agent'/'both' and restart the service.",
        ),
    ),
    "api_invalid_recover_scope": IssueDefinition(
        code="api_invalid_recover_scope",
        domain="api",
        default_severity="warning",
        summary="POST /api/v1/hardware/recover was called with an unsupported `scope` query param.",
    ),
    "api_modbus_wizard_invalid_request": IssueDefinition(
        code="api_modbus_wizard_invalid_request",
        domain="api",
        default_severity="warning",
        summary="The isolated Modbus wizard request is incomplete or unsafe.",
    ),
}


@dataclass(frozen=True)
class CodePattern:
    """A templated code family (e.g. one code per adapter id), not a fixed set.

    ``prefix``/``suffix`` bound the literal parts of an f-string code like
    ``f"adapter_{adapter_id}_not_ok"`` (prefix="adapter_", suffix="_not_ok").
    """

    prefix: str
    suffix: str
    domain: str
    default_severity: IssueSeverity
    summary: str

    def matches(self, code: str) -> bool:
        return code.startswith(self.prefix) and code.endswith(self.suffix) and len(code) > len(self.prefix) + len(self.suffix)


CODE_PATTERNS: list[CodePattern] = [
    CodePattern(
        prefix="adapter_",
        suffix="_not_ok",
        domain="hardware",
        default_severity="warning",
        summary="A specific firmware adapter's `status` is not `ok` (e.g. `adapter_modbus-io_not_ok`).",
    ),
    CodePattern(
        prefix="adapter_",
        suffix="_health_not_ok",
        domain="hardware",
        default_severity="warning",
        summary="A specific firmware adapter's health check did not report healthy (e.g. `adapter_modbus-io_health_not_ok`).",
    ),
]


def get_issue_definition(code: str) -> IssueDefinition | None:
    return ISSUE_CATALOG.get(code)


def matches_known_pattern(code: str) -> bool:
    return any(pattern.matches(code) for pattern in CODE_PATTERNS)


def all_codes() -> list[str]:
    return sorted(ISSUE_CATALOG)
