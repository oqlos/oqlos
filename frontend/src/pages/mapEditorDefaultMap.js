import { CONNECT_HARDWARE_PATHS } from "@semcod/hardware-client/paths.js";

/** Shared hardware-proxy endpoints for default MAP entries. */
const HW_DIAGNOSTIC = CONNECT_HARDWARE_PATHS.diagnosticCommand;
const HW_RUNTIME_PYTHON = CONNECT_HARDWARE_PATHS.runtimePython;

const DEFAULT_MAP = Object.freeze(
{
  "runtimeConfig": {
    "motor2": {
      "peripheralId": "motor-tic249",
      "strokeSteps": 1000,
      "cycleVolumeLiters": 5,
      "maxStepsPerSecond": 1000,
      "defaultSpeedStepsPerSecond": 1000,
      "speedUnit": "steps/s",
      "accelerationPercentPerSecond": 100,
      "accelerationUnit": "%/s",
      "limitMode": "reverse_on_limit",
      "startDirection": "right"
    }
  },
  "objectActionMap": {
    "pompa 1": {
      "Wlacz": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/pump-1",
        "handlerRuntime": "python",
        "handlerFunction": "handle_pump_on",
        "method": "POST",
        "body": {
          "peripheral_id": "pump-1",
          "command": "valve_on"
        }
      },
      "Wylacz": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/pump-1",
        "handlerRuntime": "python",
        "handlerFunction": "handle_pump_off",
        "method": "POST",
        "body": {
          "peripheral_id": "pump-1",
          "command": "valve_off"
        }
      }
    },
    "zawor testowy": {
      "Otworz": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/valve-test",
        "handlerRuntime": "js",
        "handlerFunction": "openTestValve",
        "method": "POST",
        "body": {
          "peripheral_id": "valve-test",
          "command": "valve_on"
        }
      },
      "Zamknij": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/valve-test",
        "handlerRuntime": "js",
        "handlerFunction": "closeTestValve",
        "method": "POST",
        "body": {
          "peripheral_id": "valve-test",
          "command": "valve_off"
        }
      }
    },
    "pompa DRI0050": {
      "Ustaw 10%": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/motor-dri0050",
        "handlerRuntime": "python",
        "handlerFunction": "handle_pump_set",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-dri0050",
          "command": "pump_set",
          "args": {
            "power_pct": 10
          }
        }
      },
      "Ustaw 50%": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/motor-dri0050",
        "handlerRuntime": "python",
        "handlerFunction": "handle_pump_set",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-dri0050",
          "command": "pump_set",
          "args": {
            "power_pct": 50
          }
        }
      },
      "Ustaw 100%": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/motor-dri0050",
        "handlerRuntime": "python",
        "handlerFunction": "handle_pump_set",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-dri0050",
          "command": "pump_set",
          "args": {
            "power_pct": 100
          }
        }
      },
      "Wylacz pompe": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/motor-dri0050",
        "handlerRuntime": "python",
        "handlerFunction": "handle_pump_off",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-dri0050",
          "command": "pump_off"
        }
      },
      "Status pompy": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/motor-dri0050",
        "handlerRuntime": "python",
        "handlerFunction": "handle_pump_status",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-dri0050",
          "command": "status"
        }
      }
    },
    "silnik T249": {
      "Uruchom pluco 1x": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "usb://rack-a/motor-tic249",
        "handlerRuntime": "python",
        "handlerFunction": "handle_lung_start",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-tic249",
          "command": "lung_start",
          "args": {
            "cycles": 1,
            "steps": 500,
            "speed": 1000,
            "speed_unit": "steps/s",
            "acceleration": 100,
            "acceleration_unit": "%/s",
            "pause": 0.5
          }
        }
      },
      "Uruchom pluco 3x": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "usb://rack-a/motor-tic249",
        "handlerRuntime": "python",
        "handlerFunction": "handle_lung_start",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-tic249",
          "command": "lung_start",
          "args": {
            "cycles": 3,
            "steps": 500,
            "speed": 1000,
            "speed_unit": "steps/s",
            "acceleration": 100,
            "acceleration_unit": "%/s",
            "pause": 0.5
          }
        }
      },
      "Zatrzymaj pluco": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "usb://rack-a/motor-tic249",
        "handlerRuntime": "python",
        "handlerFunction": "handle_lung_stop",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-tic249",
          "command": "lung_stop"
        }
      },
      "Wylacz silnik": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "usb://rack-a/motor-tic249",
        "handlerRuntime": "python",
        "handlerFunction": "handle_motor_disable",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-tic249",
          "command": "motor_disable"
        }
      },
      "Wlacz silnik": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "usb://rack-a/motor-tic249",
        "handlerRuntime": "python",
        "handlerFunction": "handle_motor_enable",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-tic249",
          "command": "motor_enable"
        }
      },
      "Status silnika": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "usb://rack-a/motor-tic249",
        "handlerRuntime": "python",
        "handlerFunction": "handle_motor_status",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-tic249",
          "command": "status"
        }
      },
      "Pozycja silnika": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "usb://rack-a/motor-tic249",
        "handlerRuntime": "python",
        "handlerFunction": "handle_motor_position",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-tic249",
          "command": "position"
        }
      }
    },
    "motor2": {
      "left": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "usb://rack-a/motor-tic249",
        "handlerRuntime": "python",
        "handlerFunction": "handle_motor2_move_relative",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-tic249",
          "command": "move_relative"
        },
        "args": {
          "direction": "left",
          "steps": 1000,
          "offset": -1000,
          "speed": 1000,
          "speed_unit": "steps/s",
          "max_steps_per_second": 1000,
          "acceleration": 50,
          "acceleration_unit": "%/s"
        }
      },
      "right": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "usb://rack-a/motor-tic249",
        "handlerRuntime": "python",
        "handlerFunction": "handle_motor2_move_relative",
        "method": "POST",
        "body": {
          "peripheral_id": "motor-tic249",
          "command": "move_relative"
        },
        "args": {
          "direction": "right",
          "steps": 1000,
          "offset": 1000,
          "speed": 1000,
          "speed_unit": "steps/s",
          "max_steps_per_second": 1000,
          "acceleration": 50,
          "acceleration_unit": "%/s"
        }
      }
    },
    "modul IO": {
      "Otworz zawor-1": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-io",
        "handlerRuntime": "python",
        "handlerFunction": "handle_valve_on",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-io",
          "command": "valve_on",
          "args": {
            "valve_id": "valve-1"
          }
        }
      },
      "Zamknij zawor-1": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-io",
        "handlerRuntime": "python",
        "handlerFunction": "handle_valve_off",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-io",
          "command": "valve_off",
          "args": {
            "valve_id": "valve-1"
          }
        }
      },
      "Otworz zawor-2": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-io",
        "handlerRuntime": "python",
        "handlerFunction": "handle_valve_on",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-io",
          "command": "valve_on",
          "args": {
            "valve_id": "valve-2"
          }
        }
      },
      "Zamknij zawor-2": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-io",
        "handlerRuntime": "python",
        "handlerFunction": "handle_valve_off",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-io",
          "command": "valve_off",
          "args": {
            "valve_id": "valve-2"
          }
        }
      },
      "Odczytaj wszystkie": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-io",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_all",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-io",
          "command": "read_all"
        }
      },
      "Status IO": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-io",
        "handlerRuntime": "python",
        "handlerFunction": "handle_io_status",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-io",
          "command": "status"
        }
      }
    },
    "modul ADC": {
      "Odczytaj V1": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-adc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_sensor",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-adc",
          "command": "read_sensor",
          "args": {
            "sensor_id": "v1"
          }
        }
      },
      "Odczytaj V2": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-adc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_sensor",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-adc",
          "command": "read_sensor",
          "args": {
            "sensor_id": "v2"
          }
        }
      },
      "Odczytaj V3": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-adc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_sensor",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-adc",
          "command": "read_sensor",
          "args": {
            "sensor_id": "v3"
          }
        }
      },
      "Odczytaj V4": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-adc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_sensor",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-adc",
          "command": "read_sensor",
          "args": {
            "sensor_id": "v4"
          }
        }
      },
      "Odczytaj V5": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-adc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_sensor",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-adc",
          "command": "read_sensor",
          "args": {
            "sensor_id": "v5"
          }
        }
      },
      "Odczytaj V6": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-adc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_sensor",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-adc",
          "command": "read_sensor",
          "args": {
            "sensor_id": "v6"
          }
        }
      },
      "Odczytaj V7": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-adc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_sensor",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-adc",
          "command": "read_sensor",
          "args": {
            "sensor_id": "v7"
          }
        }
      },
      "Odczytaj V8": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-adc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_sensor",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-adc",
          "command": "read_sensor",
          "args": {
            "sensor_id": "v8"
          }
        }
      },
      "Odczytaj wszystkie": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-adc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_all",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-adc",
          "command": "read_all"
        }
      },
      "Status ADC": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "modbus://rack-a/modbus-adc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_adc_status",
        "method": "POST",
        "body": {
          "peripheral_id": "modbus-adc",
          "command": "status"
        }
      }
    },
    "RTC": {
      "Status RTC": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "i2c://rack-a/rtc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_status",
        "method": "POST",
        "body": {
          "peripheral_id": "rtc",
          "command": "read_status"
        }
      },
      "Czas RTC": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "i2c://rack-a/rtc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_time",
        "method": "POST",
        "body": {
          "peripheral_id": "rtc",
          "command": "read_time"
        }
      },
      "Data RTC": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "i2c://rack-a/rtc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_date",
        "method": "POST",
        "body": {
          "peripheral_id": "rtc",
          "command": "read_date"
        }
      },
      "Temperatura RTC": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "i2c://rack-a/rtc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_temperature",
        "method": "POST",
        "body": {
          "peripheral_id": "rtc",
          "command": "read_temperature"
        }
      },
      "Watchdog RTC": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "i2c://rack-a/rtc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_read_watchdog",
        "method": "POST",
        "body": {
          "peripheral_id": "rtc",
          "command": "read_watchdog"
        }
      },
      "Sync RTC -> system": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "i2c://rack-a/rtc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_sync_to_system",
        "method": "POST",
        "body": {
          "peripheral_id": "rtc",
          "command": "sync_to_system"
        }
      },
      "Sync system -> RTC": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "i2c://rack-a/rtc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_sync_from_system",
        "method": "POST",
        "body": {
          "peripheral_id": "rtc",
          "command": "sync_from_system"
        }
      },
      "Feed watchdog": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "i2c://rack-a/rtc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_feed_watchdog",
        "method": "POST",
        "body": {
          "peripheral_id": "rtc",
          "command": "feed_watchdog"
        }
      },
      "Restart RTC": {
        "kind": "api",
        "service": "hardware-proxy",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "i2c://rack-a/rtc",
        "handlerRuntime": "python",
        "handlerFunction": "handle_restart",
        "method": "POST",
        "body": {
          "peripheral_id": "rtc",
          "command": "restart"
        }
      }
    },
    "sztuczne pluco": {
      "Ustaw 5 LPM": {
        "kind": "api",
        "service": "connect-scenario-backend",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_RUNTIME_PYTHON,
        "url": HW_RUNTIME_PYTHON,
        "hardwareAddress": "runtime://artificial-lung",
        "handlerRuntime": "python",
        "handlerFunction": "handle_set_lpm",
        "method": "POST",
        "body": {
          "peripheral_id": "artificial-lung",
          "command": "set_lpm",
          "args": {
            "lpm": 5
          }
        }
      },
      "Ustaw 10 LPM": {
        "kind": "api",
        "service": "connect-scenario-backend",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_RUNTIME_PYTHON,
        "url": HW_RUNTIME_PYTHON,
        "hardwareAddress": "runtime://artificial-lung",
        "handlerRuntime": "python",
        "handlerFunction": "handle_set_lpm",
        "method": "POST",
        "body": {
          "peripheral_id": "artificial-lung",
          "command": "set_lpm",
          "args": {
            "lpm": 10
          }
        }
      },
      "Ustaw 20 LPM": {
        "kind": "api",
        "service": "connect-scenario-backend",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_RUNTIME_PYTHON,
        "url": HW_RUNTIME_PYTHON,
        "hardwareAddress": "runtime://artificial-lung",
        "handlerRuntime": "python",
        "handlerFunction": "handle_set_lpm",
        "method": "POST",
        "body": {
          "peripheral_id": "artificial-lung",
          "command": "set_lpm",
          "args": {
            "lpm": 20
          }
        }
      },
      "Uruchom pluco": {
        "kind": "api",
        "service": "connect-scenario-backend",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_RUNTIME_PYTHON,
        "url": HW_RUNTIME_PYTHON,
        "hardwareAddress": "runtime://artificial-lung",
        "handlerRuntime": "python",
        "handlerFunction": "handle_lung_start",
        "method": "POST",
        "body": {
          "peripheral_id": "artificial-lung",
          "command": "lung_start"
        }
      },
      "Zatrzymaj pluco": {
        "kind": "api",
        "service": "connect-scenario-backend",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_RUNTIME_PYTHON,
        "url": HW_RUNTIME_PYTHON,
        "hardwareAddress": "runtime://artificial-lung",
        "handlerRuntime": "python",
        "handlerFunction": "handle_lung_stop",
        "method": "POST",
        "body": {
          "peripheral_id": "artificial-lung",
          "command": "lung_stop"
        }
      },
      "Status pluca": {
        "kind": "api",
        "service": "connect-scenario-backend",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_RUNTIME_PYTHON,
        "url": HW_RUNTIME_PYTHON,
        "hardwareAddress": "runtime://artificial-lung",
        "handlerRuntime": "python",
        "handlerFunction": "handle_lung_status",
        "method": "POST",
        "body": {
          "peripheral_id": "artificial-lung",
          "command": "lung_status"
        }
      },
      "Cykl 3x": {
        "kind": "api",
        "service": "connect-scenario-backend",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_RUNTIME_PYTHON,
        "url": HW_RUNTIME_PYTHON,
        "hardwareAddress": "runtime://artificial-lung",
        "handlerRuntime": "python",
        "handlerFunction": "handle_lung_cycle",
        "method": "POST",
        "body": {
          "peripheral_id": "artificial-lung",
          "command": "lung_cycle",
          "args": {
            "cycles": 3
          }
        }
      },
      "Inhale": {
        "kind": "api",
        "service": "connect-scenario-backend",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "usb://rack-a/motor-tic249",
        "handlerRuntime": "python",
        "handlerFunction": "handle_tic249_inhale",
        "method": "POST",
        "profiles": [
          {
            "environment": "lab",
            "usageMode": "test-run",
            "body": { "peripheral_id": "artificial-lung", "command": "tic249_inhale" },
            "args": { "tick_seconds": 1.0, "stroke_steps": 1200 }
          },
          {
            "environment": "prod",
            "usageMode": "patient",
            "body": { "peripheral_id": "artificial-lung", "command": "tic249_inhale" },
            "args": { "tick_seconds": 1.0, "stroke_steps": 900 }
          }
        ]
      },
      "Exhale": {
        "kind": "api",
        "service": "connect-scenario-backend",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "usb://rack-a/motor-tic249",
        "handlerRuntime": "python",
        "handlerFunction": "handle_tic249_exhale",
        "method": "POST",
        "profiles": [
          {
            "environment": "lab",
            "usageMode": "test-run",
            "body": { "peripheral_id": "artificial-lung", "command": "tic249_exhale" },
            "args": { "tick_seconds": 1.0, "stroke_steps": 1200 }
          },
          {
            "environment": "prod",
            "usageMode": "patient",
            "body": { "peripheral_id": "artificial-lung", "command": "tic249_exhale" },
            "args": { "tick_seconds": 1.0, "stroke_steps": 900 }
          }
        ]
      },
      "Cycle": {
        "kind": "api",
        "service": "connect-scenario-backend",
        "endpoint": HW_DIAGNOSTIC,
        "url": HW_DIAGNOSTIC,
        "hardwareAddress": "usb://rack-a/motor-tic249",
        "handlerRuntime": "python",
        "handlerFunction": "handle_tic249_cycle",
        "method": "POST",
        "profiles": [
          {
            "environment": "lab",
            "usageMode": "test-run",
            "body": { "peripheral_id": "artificial-lung", "command": "tic249_cycle" },
            "args": { "cycles": 2, "tick_seconds": 1.0, "stroke_steps": 1200 }
          },
          {
            "environment": "prod",
            "usageMode": "patient",
            "body": { "peripheral_id": "artificial-lung", "command": "tic249_cycle" },
            "args": { "cycles": 1, "tick_seconds": 1.0, "stroke_steps": 900 }
          }
        ]
      },
      "STOP AWARYJNY": {
        "kind": "api",
        "service": "connect-scenario-backend",
        "environment": "lab",
        "usageMode": "diagnostic",
        "endpoint": HW_RUNTIME_PYTHON,
        "url": HW_RUNTIME_PYTHON,
        "hardwareAddress": "runtime://artificial-lung",
        "handlerRuntime": "python",
        "handlerFunction": "handle_emergency_stop",
        "method": "POST",
        "body": {
          "peripheral_id": "artificial-lung",
          "command": "emergency_stop"
        }
      }
    }
  },
  "paramSensorMap": {
    "V1": {
      "sensor": "V1",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V1",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V1"
    },
    "V2": {
      "sensor": "V2",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V2",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V2"
    },
    "V3": {
      "sensor": "V3",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V3",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V3"
    },
    "V4": {
      "sensor": "V4",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V4",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V4"
    },
    "V5": {
      "sensor": "V5",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V5",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V5"
    },
    "V6": {
      "sensor": "V6",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V6",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V6"
    },
    "V7": {
      "sensor": "V7",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V7",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V7"
    },
    "V8": {
      "sensor": "V8",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V8",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V8"
    },
    "VI1": {
      "sensor": "V1",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V1",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V1"
    },
    "PI1": {
      "sensor": "V1",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V1",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapMaskPressure",
      "unit": "mbar",
      "inputMode": "voltage",
      "physicalInput": "V1",
      "conversionAlgorithm": "linear",
      "conversionInputUnit": "V",
      "conversionZeroPoint": 2,
      "conversionScale": 34,
      "conversionOffset": 0,
      "conversionAdcPerVolt": 3950,
      "conversionExpression": "x",
      "conversionOutputUnit": "mbar"
    },
    "VI2": {
      "sensor": "V2",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V2",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "bar",
      "inputMode": "voltage",
      "physicalInput": "V2",
      "conversionAlgorithm": "linear",
      "conversionInputUnit": "V",
      "conversionZeroPoint": 1,
      "conversionScale": 12.5,
      "conversionOffset": 0,
      "conversionAdcPerVolt": 3950,
      "conversionExpression": "x",
      "conversionOutputUnit": "bar"
    },
    "VI3": {
      "sensor": "V3",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V3",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "bar",
      "inputMode": "voltage",
      "physicalInput": "V3",
      "conversionAlgorithm": "linear",
      "conversionInputUnit": "V",
      "conversionZeroPoint": 0.5,
      "conversionScale": 200,
      "conversionOffset": 0,
      "conversionAdcPerVolt": 3950,
      "conversionExpression": "x",
      "conversionOutputUnit": "bar"
    },
    "VI4": {
      "sensor": "V4",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V4",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V4"
    },
    "VI5": {
      "sensor": "V5",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V5",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V5"
    },
    "VI6": {
      "sensor": "V6",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V6",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V6"
    },
    "VI7": {
      "sensor": "V7",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V7",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V7"
    },
    "VI8": {
      "sensor": "V8",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V8",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapVoltageInput",
      "unit": "V",
      "inputMode": "voltage",
      "physicalInput": "V8"
    },
    "Cisnienie maski": {
      "sensor": "V1",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V1",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapMaskPressure",
      "unit": "mbar",
      "inputMode": "voltage",
      "physicalInput": "V1",
      "aliasOf": "PI1"
    },
    "Przeplyw": {
      "sensor": "V2",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "modbus://rack-a/modbus-adc/V2",
      "handlerRuntime": "nodejs",
      "handlerFunction": "mapFlowRate",
      "unit": "L/min",
      "inputMode": "voltage",
      "physicalInput": "V2",
      "aliasOf": "VI2"
    },
    "Pozycja silnika": {
      "sensor": "POS",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "usb://rack-a/motor-tic249",
      "handlerRuntime": "python",
      "handlerFunction": "mapMotorPosition",
      "unit": "steps"
    },
    "Napiecie VIN": {
      "sensor": "VIN",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "usb://rack-a/motor-tic249",
      "handlerRuntime": "python",
      "handlerFunction": "mapVinVoltage",
      "unit": "mV"
    },
    "Temperatura RTC": {
      "sensor": "TEMP",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "i2c://rack-a/rtc",
      "handlerRuntime": "python",
      "handlerFunction": "mapRtcTemp",
      "unit": "C"
    },
    "LPM pluca": {
      "sensor": "LPM",
      "service": "state-api",
      "environment": "lab",
      "usageMode": "measurement",
      "endpoint": "/api/v1/state",
      "url": "/api/v1/state",
      "hardwareAddress": "runtime://artificial-lung",
      "handlerRuntime": "python",
      "handlerFunction": "mapLungLpm",
      "unit": "L/min"
    }
  },
  "actions": {
    "hui-al-start": {
      "kind": "hui-al",
      "service": "oqlos-hardware-api",
      "environment": "lab",
      "usageMode": "control",
      "endpoint": "/api/v1/hardware/hui/al/start",
      "url": "/api/v1/hardware/hui/al/start",
      "hardwareAddress": "hui://mask-tester/artificial-lung",
      "handlerRuntime": "python",
      "handlerFunction": "start_hui_artificial_lung",
      "method": "POST",
      "body": {
        "command": "hui_al_start",
        "valve_id": "valve-4",
        "direction": "right",
        "start_direction": "right",
        "limit_mode": "reverse_on_limit",
        "steps": 1000000,
        "stroke_steps": 1000000,
        "speed": 100000000,
        "cycles": 1000000,
        "pause": 0.5,
        "ramp_seconds": 0.5,
        "acceleration": 200000000
      }
    },
    "lung-pz-500x5": {
      "kind": "lung-preset",
      "service": "oqlos-hardware-api",
      "environment": "lab",
      "usageMode": "control",
      "endpoint": "/api/v1/oql/manage",
      "url": "/api/v1/oql/manage",
      "hardwareAddress": "hui://mask-tester/artificial-lung/pz-500x5",
      "handlerRuntime": "python",
      "handlerFunction": "set_lung",
      "method": "POST",
      "body": {
        "command": "lung",
        "steps": 500,
        "speed": 10000000,
        "cycles": 5,
        "pause": 0.5
      }
    },
    "lung-pz-1000x3": {
      "kind": "lung-preset",
      "service": "oqlos-hardware-api",
      "environment": "lab",
      "usageMode": "control",
      "endpoint": "/api/v1/oql/manage",
      "url": "/api/v1/oql/manage",
      "hardwareAddress": "hui://mask-tester/artificial-lung/pz-1000x3",
      "handlerRuntime": "python",
      "handlerFunction": "set_lung",
      "method": "POST",
      "body": {
        "command": "lung",
        "steps": 1000,
        "speed": 10000000,
        "cycles": 3,
        "pause": 0.5
      }
    },
    "head-inflate": {
      "kind": "hui-hold",
      "service": "oqlos-hardware-api",
      "environment": "lab",
      "usageMode": "control",
      "endpoint": "/api/v1/hardware/hui/hold/head-inflate/start",
      "url": "/api/v1/hardware/hui/hold/head-inflate/start",
      "hardwareAddress": "hui://mask-tester/head-inflate",
      "handlerRuntime": "python",
      "handlerFunction": "start_hui_hold",
      "method": "POST",
      "body": {
        "command": "hui_hold",
        "key": "head-inflate",
        "valves_on": ["valve-5", "valve-2"],
        "pump_pct": 70
      }
    },
    "head-deflate": {
      "kind": "hui-hold",
      "service": "oqlos-hardware-api",
      "environment": "lab",
      "usageMode": "control",
      "endpoint": "/api/v1/hardware/hui/hold/head-deflate/start",
      "url": "/api/v1/hardware/hui/hold/head-deflate/start",
      "hardwareAddress": "hui://mask-tester/head-deflate",
      "handlerRuntime": "python",
      "handlerFunction": "start_hui_hold",
      "method": "POST",
      "body": {
        "command": "hui_hold",
        "key": "head-deflate",
        "valves_on": ["valve-3", "valve-6"],
        "pump_pct": 0
      }
    },
    "lp-pwm-plus5": {
      "kind": "hui-hold",
      "service": "oqlos-hardware-api",
      "environment": "lab",
      "usageMode": "control",
      "endpoint": "/api/v1/hardware/hui/hold/lp-pwm-plus5/start",
      "url": "/api/v1/hardware/hui/hold/lp-pwm-plus5/start",
      "hardwareAddress": "hui://mask-tester/lp-pwm-plus5",
      "handlerRuntime": "python",
      "handlerFunction": "start_hui_hold",
      "method": "POST",
      "body": {
        "command": "hui_hold",
        "key": "lp-pwm-plus5",
        "valves_on": ["valve-5"],
        "pump_pct": 50
      }
    },
    "lp-pwm-plus10": {
      "kind": "hui-hold",
      "service": "oqlos-hardware-api",
      "environment": "lab",
      "usageMode": "control",
      "endpoint": "/api/v1/hardware/hui/hold/lp-pwm-plus10/start",
      "url": "/api/v1/hardware/hui/hold/lp-pwm-plus10/start",
      "hardwareAddress": "hui://mask-tester/lp-pwm-plus10",
      "handlerRuntime": "python",
      "handlerFunction": "start_hui_hold",
      "method": "POST",
      "body": {
        "command": "hui_hold",
        "key": "lp-pwm-plus10",
        "valves_on": ["valve-5"],
        "pump_pct": 100
      }
    },
    "lp-pwm-minus5": {
      "kind": "hui-hold",
      "service": "oqlos-hardware-api",
      "environment": "lab",
      "usageMode": "control",
      "endpoint": "/api/v1/hardware/hui/hold/lp-pwm-minus5/start",
      "url": "/api/v1/hardware/hui/hold/lp-pwm-minus5/start",
      "hardwareAddress": "hui://mask-tester/lp-pwm-minus5",
      "handlerRuntime": "python",
      "handlerFunction": "start_hui_hold",
      "method": "POST",
      "body": {
        "command": "hui_hold",
        "key": "lp-pwm-minus5",
        "valves_on": ["valve-6"],
        "pump_pct": 50
      }
    },
    "lp-pwm-minus10": {
      "kind": "hui-hold",
      "service": "oqlos-hardware-api",
      "environment": "lab",
      "usageMode": "control",
      "endpoint": "/api/v1/hardware/hui/hold/lp-pwm-minus10/start",
      "url": "/api/v1/hardware/hui/hold/lp-pwm-minus10/start",
      "hardwareAddress": "hui://mask-tester/lp-pwm-minus10",
      "handlerRuntime": "python",
      "handlerFunction": "start_hui_hold",
      "method": "POST",
      "body": {
        "command": "hui_hold",
        "key": "lp-pwm-minus10",
        "valves_on": ["valve-6"],
        "pump_pct": 100
      }
    },
    "lp-bleed": {
      "kind": "hui-hold",
      "service": "oqlos-hardware-api",
      "environment": "lab",
      "usageMode": "control",
      "endpoint": "/api/v1/hardware/hui/hold/lp-bleed/start",
      "url": "/api/v1/hardware/hui/hold/lp-bleed/start",
      "hardwareAddress": "hui://mask-tester/lp-bleed",
      "handlerRuntime": "python",
      "handlerFunction": "start_hui_hold",
      "method": "POST",
      "body": {
        "command": "hui_hold",
        "key": "lp-bleed",
        "valves_on": ["valve-4"],
        "pump_pct": 0
      }
    },
    "wc-press": {
      "kind": "hui-valve",
      "service": "oqlos-hardware-api",
      "environment": "lab",
      "usageMode": "control",
      "endpoint": "/api/v1/hardware/hui/valve/wc-press",
      "url": "/api/v1/hardware/hui/valve/wc-press",
      "hardwareAddress": "hui://mask-tester/wc-press",
      "handlerRuntime": "python",
      "handlerFunction": "run_hui_valve_key",
      "method": "POST",
      "body": {
        "command": "hui_valve",
        "key": "wc-press",
        "valve_id": "valve-wc",
        "value": true
      }
    },
    "wc-bleed": {
      "kind": "hui-valve",
      "service": "oqlos-hardware-api",
      "environment": "lab",
      "usageMode": "control",
      "endpoint": "/api/v1/hardware/hui/valve/wc-bleed",
      "url": "/api/v1/hardware/hui/valve/wc-bleed",
      "hardwareAddress": "hui://mask-tester/wc-bleed",
      "handlerRuntime": "python",
      "handlerFunction": "run_hui_valve_key",
      "method": "POST",
      "body": {
        "command": "hui_valve",
        "key": "wc-bleed",
        "valve_id": "valve-wc",
        "value": false
      }
    },
    "Reset alarmu": {
      "kind": "api",
      "service": "hardware-proxy",
      "environment": "lab",
      "usageMode": "diagnostic",
      "endpoint": HW_DIAGNOSTIC,
      "url": HW_DIAGNOSTIC,
      "hardwareAddress": "modbus://rack-a/main-controller",
      "handlerRuntime": "python",
      "handlerFunction": "resetAlarm",
      "method": "POST",
      "body": {
        "peripheral_id": "main-controller",
        "command": "alarm_reset"
      }
    },
    "Pobierz status": {
      "kind": "api",
      "service": "hardware-proxy",
      "environment": "lab",
      "usageMode": "diagnostic",
      "endpoint": HW_DIAGNOSTIC,
      "url": HW_DIAGNOSTIC,
      "hardwareAddress": "modbus://rack-a/main-controller",
      "handlerRuntime": "python",
      "handlerFunction": "readMainStatus",
      "method": "POST",
      "body": {
        "peripheral_id": "main-controller",
        "command": "status"
      }
    },
    "Odczytaj wszystkie zawory": {
      "kind": "api",
      "service": "hardware-proxy",
      "environment": "lab",
      "usageMode": "diagnostic",
      "endpoint": HW_DIAGNOSTIC,
      "url": HW_DIAGNOSTIC,
      "hardwareAddress": "modbus://rack-a/modbus-io",
      "handlerRuntime": "python",
      "handlerFunction": "readAllValves",
      "method": "POST",
      "body": {
        "peripheral_id": "modbus-io",
        "command": "read_all"
      }
    },
    "Odczytaj wszystkie sensory": {
      "kind": "api",
      "service": "hardware-proxy",
      "environment": "lab",
      "usageMode": "diagnostic",
      "endpoint": HW_DIAGNOSTIC,
      "url": HW_DIAGNOSTIC,
      "hardwareAddress": "modbus://rack-a/modbus-adc",
      "handlerRuntime": "python",
      "handlerFunction": "readAllSensors",
      "method": "POST",
      "body": {
        "peripheral_id": "modbus-adc",
        "command": "read_all"
      }
    },
    "Sync RTC -> system": {
      "kind": "api",
      "service": "hardware-proxy",
      "environment": "lab",
      "usageMode": "diagnostic",
      "endpoint": HW_DIAGNOSTIC,
      "url": HW_DIAGNOSTIC,
      "hardwareAddress": "i2c://rack-a/rtc",
      "handlerRuntime": "python",
      "handlerFunction": "syncRtcToSystem",
      "method": "POST",
      "body": {
        "peripheral_id": "rtc",
        "command": "sync_to_system"
      }
    },
    "Sync system -> RTC": {
      "kind": "api",
      "service": "hardware-proxy",
      "environment": "lab",
      "usageMode": "diagnostic",
      "endpoint": HW_DIAGNOSTIC,
      "url": HW_DIAGNOSTIC,
      "hardwareAddress": "i2c://rack-a/rtc",
      "handlerRuntime": "python",
      "handlerFunction": "syncSystemToRtc",
      "method": "POST",
      "body": {
        "peripheral_id": "rtc",
        "command": "sync_from_system"
      }
    },
    "Feed watchdog": {
      "kind": "api",
      "service": "hardware-proxy",
      "environment": "lab",
      "usageMode": "diagnostic",
      "endpoint": HW_DIAGNOSTIC,
      "url": HW_DIAGNOSTIC,
      "hardwareAddress": "i2c://rack-a/rtc",
      "handlerRuntime": "python",
      "handlerFunction": "feedWatchdog",
      "method": "POST",
      "body": {
        "peripheral_id": "rtc",
        "command": "feed_watchdog"
      }
    },
    "Restart RTC": {
      "kind": "api",
      "service": "hardware-proxy",
      "environment": "lab",
      "usageMode": "diagnostic",
      "endpoint": HW_DIAGNOSTIC,
      "url": HW_DIAGNOSTIC,
      "hardwareAddress": "i2c://rack-a/rtc",
      "handlerRuntime": "python",
      "handlerFunction": "restartRtc",
      "method": "POST",
      "body": {
        "peripheral_id": "rtc",
        "command": "restart"
      }
    }
  },
  "funcImplementations": {
    "Start testu szczelnosci": {
      "kind": "sequence",
      "service": "connect-scenario-backend",
      "environment": "lab",
      "usageMode": "test-run",
      "endpoint": HW_RUNTIME_PYTHON,
      "hardwareAddress": "pipeline://leak-test/start",
      "handlerRuntime": "python",
      "handlerFunction": "handle_leak_test_start",
      "steps": [
        {
          "action": "Wlacz",
          "object": "pompa 1"
        },
        {
          "action": "Otworz",
          "object": "zawor testowy"
        }
      ]
    },
    "Stop testu szczelnosci": {
      "kind": "sequence",
      "service": "connect-scenario-backend",
      "environment": "lab",
      "usageMode": "test-run",
      "endpoint": HW_RUNTIME_PYTHON,
      "hardwareAddress": "pipeline://leak-test/stop",
      "handlerRuntime": "python",
      "handlerFunction": "handle_leak_test_stop",
      "steps": [
        {
          "action": "Zamknij",
          "object": "zawor testowy"
        },
        {
          "action": "Wylacz",
          "object": "pompa 1"
        }
      ]
    },
    "Test zaworu 1": {
      "kind": "sequence",
      "service": "connect-scenario-backend",
      "environment": "lab",
      "usageMode": "test-run",
      "endpoint": HW_RUNTIME_PYTHON,
      "hardwareAddress": "pipeline://valve-1-test",
      "handlerRuntime": "python",
      "handlerFunction": "handle_valve1_test",
      "steps": [
        {
          "action": "Otworz zawor-1",
          "object": "modul IO"
        },
        {
          "action": "Status IO",
          "object": "modul IO"
        },
        {
          "action": "Zamknij zawor-1",
          "object": "modul IO"
        }
      ]
    },
    "Test zaworu 2": {
      "kind": "sequence",
      "service": "connect-scenario-backend",
      "environment": "lab",
      "usageMode": "test-run",
      "endpoint": HW_RUNTIME_PYTHON,
      "hardwareAddress": "pipeline://valve-2-test",
      "handlerRuntime": "python",
      "handlerFunction": "handle_valve2_test",
      "steps": [
        {
          "action": "Otworz zawor-2",
          "object": "modul IO"
        },
        {
          "action": "Status IO",
          "object": "modul IO"
        },
        {
          "action": "Zamknij zawor-2",
          "object": "modul IO"
        }
      ]
    },
    "Test pompy DRI0050": {
      "kind": "sequence",
      "service": "connect-scenario-backend",
      "environment": "lab",
      "usageMode": "test-run",
      "endpoint": HW_RUNTIME_PYTHON,
      "hardwareAddress": "pipeline://pump-test",
      "handlerRuntime": "python",
      "handlerFunction": "handle_pump_test",
      "steps": [
        {
          "action": "Ustaw 10%",
          "object": "pompa DRI0050"
        },
        {
          "action": "Status pompy",
          "object": "pompa DRI0050"
        },
        {
          "action": "Ustaw 50%",
          "object": "pompa DRI0050"
        },
        {
          "action": "Status pompy",
          "object": "pompa DRI0050"
        },
        {
          "action": "Wylacz pompe",
          "object": "pompa DRI0050"
        }
      ]
    },
    "Test silnika T249": {
      "kind": "sequence",
      "service": "connect-scenario-backend",
      "environment": "lab",
      "usageMode": "test-run",
      "endpoint": HW_RUNTIME_PYTHON,
      "hardwareAddress": "pipeline://motor-test",
      "handlerRuntime": "python",
      "handlerFunction": "handle_motor_test",
      "steps": [
        {
          "action": "Wlacz silnik",
          "object": "silnik T249"
        },
        {
          "action": "Status silnika",
          "object": "silnik T249"
        },
        {
          "action": "Pozycja silnika",
          "object": "silnik T249"
        },
        {
          "action": "Wylacz silnik",
          "object": "silnik T249"
        }
      ]
    },
    "Test modulu ADC": {
      "kind": "sequence",
      "service": "connect-scenario-backend",
      "environment": "lab",
      "usageMode": "test-run",
      "endpoint": HW_RUNTIME_PYTHON,
      "hardwareAddress": "pipeline://adc-test",
      "handlerRuntime": "python",
      "handlerFunction": "handle_adc_test",
      "steps": [
        {
          "action": "Odczytaj wszystkie",
          "object": "modul ADC"
        },
        {
          "action": "Status ADC",
          "object": "modul ADC"
        }
      ]
    },
    "Test RTC": {
      "kind": "sequence",
      "service": "connect-scenario-backend",
      "environment": "lab",
      "usageMode": "test-run",
      "endpoint": HW_RUNTIME_PYTHON,
      "hardwareAddress": "pipeline://rtc-test",
      "handlerRuntime": "python",
      "handlerFunction": "handle_rtc_test",
      "steps": [
        {
          "action": "Status RTC",
          "object": "RTC"
        },
        {
          "action": "Czas RTC",
          "object": "RTC"
        },
        {
          "action": "Temperatura RTC",
          "object": "RTC"
        },
        {
          "action": "Watchdog RTC",
          "object": "RTC"
        }
      ]
    },
    "Test sztucznego pluca": {
      "kind": "sequence",
      "service": "connect-scenario-backend",
      "environment": "lab",
      "usageMode": "test-run",
      "endpoint": HW_RUNTIME_PYTHON,
      "hardwareAddress": "pipeline://lung-test",
      "handlerRuntime": "python",
      "handlerFunction": "handle_lung_test",
      "steps": [
        {
          "action": "Ustaw 10 LPM",
          "object": "sztuczne pluco"
        },
        {
          "action": "Uruchom pluco",
          "object": "sztuczne pluco"
        },
        {
          "action": "Status pluca",
          "object": "sztuczne pluco"
        },
        {
          "action": "Zatrzymaj pluco",
          "object": "sztuczne pluco"
        }
      ]
    },
    "Test cyklu oddechowego": {
      "kind": "sequence",
      "service": "connect-scenario-backend",
      "environment": "lab",
      "usageMode": "test-run",
      "endpoint": HW_RUNTIME_PYTHON,
      "hardwareAddress": "pipeline://breath-cycle",
      "handlerRuntime": "python",
      "handlerFunction": "handle_breath_cycle",
      "steps": [
        {
          "action": "Ustaw 10 LPM",
          "object": "sztuczne pluco"
        },
        {
          "action": "Cykl 3x",
          "object": "sztuczne pluco"
        },
        {
          "action": "Status pluca",
          "object": "sztuczne pluco"
        }
      ]
    },
    "Pelny test peryferiow": {
      "kind": "sequence",
      "service": "connect-scenario-backend",
      "environment": "lab",
      "usageMode": "test-run",
      "endpoint": HW_RUNTIME_PYTHON,
      "hardwareAddress": "pipeline://full-test",
      "handlerRuntime": "python",
      "handlerFunction": "handle_full_test",
      "steps": [
        {
          "action": "Status IO",
          "object": "modul IO"
        },
        {
          "action": "Status ADC",
          "object": "modul ADC"
        },
        {
          "action": "Status pompy",
          "object": "pompa DRI0050"
        },
        {
          "action": "Status silnika",
          "object": "silnik T249"
        },
        {
          "action": "Status RTC",
          "object": "RTC"
        },
        {
          "action": "Status pluca",
          "object": "sztuczne pluco"
        }
      ]
    }
  }
}
);

export default DEFAULT_MAP;
