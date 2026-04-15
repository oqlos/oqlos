"""Firmware service configuration.

Shared constants used by the firmware FastAPI app and its routers.
"""

from __future__ import annotations

import os
from pathlib import Path

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
    firmware_port: int = 8202
    service_name: str = "firmware-simulator"
    service_version: str = "0.1.0"
    
    # Hardware Configuration
    hardware_mode: str = "mock"
    
    # Modbus RTU Configuration
    modbus_serial_port: str = "/dev/ttyACM1"
    modbus_baud: int = 19200
    modbus_parity: str = "N"
    modbus_device_id: int = 1
    
    # Modbus TCP Fallback
    modbus_host: str = "localhost"
    modbus_port: int = 502
    
    # Hardware Service URLs
    piadc_url: str = "http://localhost:8080"
    motor_url: str = "http://localhost:49055"
    lung_motor_url: str = "http://localhost:8205"
    
    # Pump Calibration
    pump_flow_full_scale_lpm: float = 10.0

    # Logging
    log_level: str = "INFO"
    
    # CORS Settings
    cors_origins: str = "*"


# Load settings
_settings = Settings()
SERVICE_NAME = _settings.service_name
SERVICE_VERSION = resolve_release_version(Path(__file__).resolve().parent)
FIRMWARE_PORT = _settings.firmware_port

# Export settings for use in other modules
def get_settings() -> Settings:
    """Get the application settings instance."""
    return _settings
