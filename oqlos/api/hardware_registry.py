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
        "name": "2x M5Stack 4In8Out (16 OUT / 8 IN via CoreS3)",
        # Alternative valve stage: listed so operators see it, but a stand that
        # has not been rewired must not be pushed into live scans because of it.
        "optional": True,
        "version": "13.2",
        "protocol": "HTTP/WiFi to CoreS3, then I2C",
        "description": "16 MOSFET outputs + 8 contact inputs on two modules - primary valve controller with modbus-io fallback",
        "repo": "m5-4in8out",
        "digital_outputs": "OUT1-OUT16 (2x 8 AO3400A MOSFET, common anode, 1A/channel, 9-24V)",
        "digital_inputs": "IN1-IN8 (2x 4 passive dry contact, no active signal above 5V)",
        "interface": "BoardNet HTTP -> CoreS3 WiFi -> I2C modules 0x45 + 0x66",
        "default_config": "CoreS3 :8080; addresses 0x45 + 0x66, 100 kHz; outputs 0x20+n, inputs 0x10+n",
        "wiki": "https://docs.m5stack.com/en/module/4in8out",
    },
]
