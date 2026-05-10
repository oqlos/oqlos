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
        default=19200,
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
        default=1,
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
    
    # CORS Settings
    cors_origins: str = Field(
        default="*",
        validation_alias=AliasChoices("OQLOS_CORS_ORIGINS", "CORS_ORIGINS"),
    )


# Load settings
_settings = Settings()
SERVICE_NAME = _settings.service_name
SERVICE_VERSION = resolve_release_version(Path(__file__).resolve().parent)
FIRMWARE_PORT = _settings.firmware_port

# Export settings for use in other modules
def get_settings() -> Settings:
    """Get the application settings instance."""
    return _settings
