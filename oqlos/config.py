"""Firmware service configuration.

Shared constants used by the firmware FastAPI app and its routers.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from oqlos.shared.release_version import resolve_release_version


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Server Configuration
    firmware_port: int = Field(
        default=8202,
        validation_alias=AliasChoices("OQLOS_FIRMWARE_PORT", "FIRMWARE_PORT"),
    )
    service_name: str = Field(
        default="firmware-simulator",
        validation_alias=AliasChoices("OQLOS_SERVICE_NAME", "SERVICE_NAME"),
    )
    service_version: str = Field(
        default="0.1.0",
        validation_alias=AliasChoices("OQLOS_SERVICE_VERSION", "SERVICE_VERSION"),
    )
    
    # Hardware Configuration
    hardware_mode: str = Field(
        default="real",
        validation_alias=AliasChoices("OQLOS_HARDWARE_MODE", "HARDWARE_MODE"),
    )
    
    # Modbus RTU Configuration
    modbus_serial_port: str = Field(
        default="/dev/ttyACM1",
        validation_alias=AliasChoices(
            "OQLOS_MODBUS_SERIAL_PORT",
            "MODBUS_SERIAL_PORT",
            "OQLOS_MODBUS_BUS_SERIAL_PORT",
            "MODBUS_BUS_SERIAL_PORT",
        ),
    )
    modbus_baud: int = Field(
        default=4800,
        validation_alias=AliasChoices(
            "OQLOS_MODBUS_BAUD",
            "MODBUS_BAUD",
            "MODBUS_BAUD_RATE",
            "OQLOS_MODBUS_BUS_BAUD",
            "MODBUS_BUS_BAUD",
        ),
    )
    modbus_parity: str = Field(
        default="N",
        validation_alias=AliasChoices(
            "OQLOS_MODBUS_PARITY",
            "MODBUS_PARITY",
            "OQLOS_MODBUS_BUS_PARITY",
            "MODBUS_BUS_PARITY",
        ),
    )
    modbus_device_id: int = Field(
        default=2,
        validation_alias=AliasChoices("OQLOS_MODBUS_DEVICE_ID", "MODBUS_DEVICE_ID"),
    )

    # Modbus RTU Analog Input 8CH Configuration
    modbus_adc_serial_port: str = Field(
        default="/dev/ttyUSB0",
        validation_alias=AliasChoices(
            "OQLOS_MODBUS_ADC_SERIAL_PORT",
            "MODBUS_ADC_SERIAL_PORT",
            "OQLOS_MODBUS_BUS_SERIAL_PORT",
            "MODBUS_BUS_SERIAL_PORT",
        ),
    )
    modbus_adc_baud: int = Field(
        default=9600,
        validation_alias=AliasChoices(
            "OQLOS_MODBUS_ADC_BAUD",
            "MODBUS_ADC_BAUD",
            "MODBUS_ADC_BAUD_RATE",
            "OQLOS_MODBUS_BUS_BAUD",
            "MODBUS_BUS_BAUD",
        ),
    )
    modbus_adc_parity: str = Field(
        default="N",
        validation_alias=AliasChoices(
            "OQLOS_MODBUS_ADC_PARITY",
            "MODBUS_ADC_PARITY",
            "OQLOS_MODBUS_BUS_PARITY",
            "MODBUS_BUS_PARITY",
        ),
    )
    modbus_adc_device_id: int = Field(
        default=1,
        validation_alias=AliasChoices("OQLOS_MODBUS_ADC_DEVICE_ID", "MODBUS_ADC_DEVICE_ID"),
    )
    modbus_adc_read_address: int = Field(
        default=0,
        validation_alias=AliasChoices("OQLOS_MODBUS_ADC_READ_ADDRESS", "MODBUS_ADC_READ_ADDRESS"),
    )
    modbus_adc_read_count: int = Field(
        default=8,
        validation_alias=AliasChoices("OQLOS_MODBUS_ADC_READ_COUNT", "MODBUS_ADC_READ_COUNT"),
    )
    
    # Modbus TCP Fallback
    modbus_host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("OQLOS_MODBUS_HOST", "MODBUS_HOST"),
    )
    modbus_port: int = Field(
        default=502,
        validation_alias=AliasChoices("OQLOS_MODBUS_PORT", "MODBUS_PORT"),
    )
    
    # Hardware Service URLs
    piadc_url: str = Field(
        default="http://localhost:8080",
        validation_alias=AliasChoices("OQLOS_PIADC_URL", "PIADC_URL"),
    )
    motor_url: str = Field(
        default="http://localhost:49055",
        validation_alias=AliasChoices("OQLOS_MOTOR_URL", "MOTOR_URL"),
    )
    lung_motor_url: str = Field(
        default="http://localhost:8205",
        validation_alias=AliasChoices("OQLOS_LUNG_MOTOR_URL", "LUNG_MOTOR_URL"),
    )
    usb_adc_stack_url: str = Field(
        default="http://127.0.0.1:8214",
        validation_alias=AliasChoices("OQLOS_USB_ADC_STACK_URL", "USB_ADC_STACK_URL"),
    )
    adc_source: str = Field(
        default="auto",
        validation_alias=AliasChoices("OQLOS_ADC_SOURCE", "ADC_SOURCE"),
        description="Analog input source: auto, usb-adc-stack, or modbus-adc",
    )
    usb_adc_timeout_seconds: float = Field(
        default=3.0,
        validation_alias=AliasChoices("OQLOS_USB_ADC_TIMEOUT_SECONDS", "USB_ADC_TIMEOUT_SECONDS"),
        ge=0.05,
        le=10.0,
    )
    
    # Pump Calibration
    pump_flow_full_scale_lpm: float = Field(
        default=10.0,
        validation_alias=AliasChoices("OQLOS_PUMP_FLOW_FULL_SCALE_LPM", "PUMP_FLOW_FULL_SCALE_LPM"),
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("OQLOS_LOG_LEVEL", "LOG_LEVEL"),
    )
    log_file: str = Field(
        default="",
        validation_alias=AliasChoices("OQLOS_LOG_FILE", "OQLOS_HARDWARE_LOG_FILE"),
        description="Optional log file path (e.g. ~/maskservice/logs/oqlos-hardware-api.log)",
    )
    log_max_bytes: int = Field(
        default=10_000_000,
        validation_alias="OQLOS_LOG_MAX_BYTES",
        ge=100_000,
        le=1_000_000_000,
        description="Maximum size of one OqlOS rotating log file in bytes",
    )
    log_backup_count: int = Field(
        default=5,
        validation_alias="OQLOS_LOG_BACKUP_COUNT",
        ge=1,
        le=50,
        description="Number of rotated OqlOS log files retained",
    )
    http_client_log_level: str = Field(
        default="WARNING",
        validation_alias="OQLOS_HTTP_CLIENT_LOG_LEVEL",
        description="Log level for noisy httpx/httpcore transport loggers",
    )
    
    # CORS Settings
    cors_origins: str = Field(
        default="*",
        validation_alias=AliasChoices("OQLOS_CORS_ORIGINS", "CORS_ORIGINS"),
    )

    # ------------------------------------------------------------------
    # OQL-over-MQTT transport (inter-node hardware control)
    # ------------------------------------------------------------------
    # role: off | controller | agent | both
    #   off        — no MQTT transport (default; preserves single-process behavior)
    #   controller — publish OQL and await responses (runs on the app node, e.g. pi109)
    #   agent      — subscribe, execute OQL against local hardware, reply (runs on the hardware Pi)
    #   both       — start both against the same broker (dev/loopback)
    oql_transport_role: str = Field(
        default="off",
        validation_alias=AliasChoices("OQLOS_OQL_TRANSPORT_ROLE", "OQL_TRANSPORT_ROLE"),
    )
    # Identifies the hardware node. The controller targets this id; the agent answers for it.
    oql_node_id: str = Field(
        default="default",
        validation_alias=AliasChoices("OQLOS_OQL_NODE_ID", "OQL_NODE_ID"),
    )
    oql_mqtt_host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("OQLOS_OQL_MQTT_HOST", "OQL_MQTT_HOST", "OQLOS_MQTT_HOST"),
    )
    oql_mqtt_port: int = Field(
        default=1883,
        validation_alias=AliasChoices("OQLOS_OQL_MQTT_PORT", "OQL_MQTT_PORT", "OQLOS_MQTT_PORT"),
    )
    oql_mqtt_username: str = Field(
        default="",
        validation_alias=AliasChoices("OQLOS_OQL_MQTT_USERNAME", "OQL_MQTT_USERNAME"),
    )
    oql_mqtt_password: str = Field(
        default="",
        validation_alias=AliasChoices("OQLOS_OQL_MQTT_PASSWORD", "OQL_MQTT_PASSWORD"),
    )
    oql_topic_prefix: str = Field(
        default="oqlos/c2004",
        validation_alias=AliasChoices("OQLOS_OQL_TOPIC_PREFIX", "OQL_TOPIC_PREFIX"),
    )
    oql_default_timeout_ms: int = Field(
        default=15000,
        validation_alias=AliasChoices("OQLOS_OQL_TIMEOUT_MS", "OQL_TIMEOUT_MS"),
    )


# Load settings
_settings = Settings()
SERVICE_NAME = _settings.service_name
SERVICE_VERSION = resolve_release_version(Path(__file__).resolve().parents[1])
FIRMWARE_PORT = _settings.firmware_port

# Export settings for use in other modules
def get_settings() -> Settings:
    """Get the application settings instance."""
    return _settings
