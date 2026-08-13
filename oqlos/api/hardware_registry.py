"""Static hardware adapter registry for identify/probe flows."""

from __future__ import annotations

from typing import Any

HARDWARE_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "modbus-adc",
        "name": "Waveshare Modbus RTU Analog Input 8CH",
        "version": "1.0.0",
        "protocol": "Modbus RTU (RS485)",
        "description": "8-channel analog input module - pressure sensors",
        "repo": "waveshare-modbus-rtu-analog-input-8ch",
        "channels": {
            "0": "AI01 NC sensor",
            "1": "AI02 SC sensor",
            "2": "AI03 WC sensor",
            "3": "AI04 spare",
            "4": "AI05 spare",
            "5": "AI06 spare",
            "6": "AI07 spare",
            "7": "AI08 spare",
        },
        "interface": "RS485 via USB serial adapter",
        "default_config": "4800 baud, N-8-1, slave address 1, input registers 0x0000-0x0007",
        "wiki": "https://www.waveshare.com/wiki/Modbus_RTU_Analog_Input_8CH",
    },
    {
        "id": "motor-tic249",
        "name": "Pololu Tic T249",
        "version": "0.1.13",
        "protocol": "USB + REST",
        "description": "Stepper motor controller - artificial lung pump",
        "repo": "rpi-motor-tic249",
        "capabilities": ["reciprocate", "homing", "limit-switches"],
    },
    {
        "id": "motor-dri0050",
        "name": "DFRobot DRI0050",
        "version": "1.0.0",
        "protocol": "MODBUS RTU (serial)",
        "description": "PWM motor & LED strip driver",
        "repo": "rpi-motor-DRI0050",
        "registers": ["PID", "VID", "Duty", "Frequency", "Enable"],
    },
    {
        "id": "modbus-io",
        "name": "Waveshare Modbus RTU IO 8CH",
        "version": "V2.00",
        "protocol": "Modbus RTU (RS485)",
        "description": "8DI + 8DO industrial I/O module - valve & signal control",
        "repo": "pimodbus",
        "digital_outputs": "DO1-DO8 (5-40V, open-drain, 500mA/ch)",
        "digital_inputs": "DI1-DI8 (5-36V, optocoupler isolated)",
        "interface": "RS485 via USB serial adapter",
        "default_config": "4800 baud, N-8-1, slave address 1",
        "wiki": "https://www.waveshare.com/wiki/Modbus_RTU_IO_8CH",
    },
    {
        "id": "io-m5-4in8out",
        "name": "M5Stack Module 4In8Out",
        # Alternative valve stage: listed so operators see it, but a stand that
        # has not been rewired must not be pushed into live scans because of it.
        "optional": True,
        "version": "13.2",
        "protocol": "I2C",
        "description": "8 MOSFET outputs + 4 contact inputs - valve control (alternative to modbus-io)",
        "repo": "m5-4in8out",
        "digital_outputs": "OUT1-OUT8 (AO3400A MOSFET, common anode, 1A/ch, 8A total, 9-24V)",
        "digital_inputs": "IN1-IN4 (passive dry contact only, no active signal above 5V)",
        "interface": "I2C via Raspberry Pi /dev/i2c-1 or MCP2221A USB-I2C adapter",
        "default_config": "address 0x45, 100 kHz; outputs 0x20+n, inputs 0x10+n, version 0xFE",
        "wiki": "https://docs.m5stack.com/en/module/4in8out",
    },
]
