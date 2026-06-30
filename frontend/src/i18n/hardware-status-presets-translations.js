// Auto-generated preset UI strings for hardware status (6 langs)
export const hardwareStatusPresetsByLang = {
  "pl": {
    "preset": {
      "modbus_io": {
        "label": "Waveshare Modbus RTU IO 8CH",
        "protocol": "Modbus RTU (RS485)",
        "cmd": {
          "valve_on_1": "Zawór ON (valve-1)",
          "valve_off_1": "Zawór OFF (valve-1)",
          "valve_on_2": "Zawór ON (valve-2)",
          "valve_off_2": "Zawór OFF (valve-2)",
          "read_all": "Odczyt wszystkich zaworów",
          "status": "Status IO"
        }
      },
      "motor_dri0050": {
        "label": "DFRobot DRI0050",
        "protocol": "MODBUS RTU (szeregowy)",
        "cmd": {
          "pump_10": "Pompa 10%",
          "pump_20": "Pompa 20%",
          "pump_50": "Pompa 50%",
          "pump_80": "Pompa 80%",
          "pump_100": "Pompa 100%",
          "pump_off": "Pompa OFF",
          "status": "Status pompy"
        }
      },
      "motor_tic249": {
        "label": "Pololu Tic T249",
        "protocol": "USB + REST",
        "cmd": {
          "lung_start_1": "Start płuca (1 cykl, 1000 kroków/s)",
          "lung_start_3": "Start płuca (3 cykle)",
          "lung_start_5": "Start płuca (5 cykli)",
          "lung_stop": "Stop płuca",
          "motor_disable": "Wyłącz silnik (bez zasilania)",
          "motor_enable": "Włącz silnik",
          "status": "Status silnika",
          "position": "Pozycja"
        }
      },
      "modbus_adc": {
        "label": "Waveshare Modbus RTU Analog Input 8CH",
        "protocol": "Modbus RTU (RS485)",
        "cmd": {
          "read_v1": "Napięcie V1",
          "read_v2": "Napięcie V2",
          "read_v3": "Napięcie V3",
          "read_v4": "Napięcie V4",
          "read_v5": "Napięcie V5",
          "read_v6": "Napięcie V6",
          "read_v7": "Napięcie V7",
          "read_v8": "Napięcie V8",
          "read_all": "Odczyt wszystkich sensorów",
          "status": "Status ADC"
        }
      },
      "rtc": {
        "label": "Waveshare RTC WatchDog HAT (DS3231)",
        "protocol": "I2C (piRTC sidecar HTTP)",
        "cmd": {
          "read_status": "Odczyt statusu",
          "read_time": "Odczyt czasu",
          "read_date": "Odczyt daty",
          "read_temperature": "Temperatura",
          "read_watchdog": "Status watchdog",
          "sync_to_system": "Sync RTC → system",
          "sync_from_system": "Sync system → RTC",
          "feed_watchdog": "Zasil watchdog",
          "restart": "Restart (reinit HW)"
        }
      },
      "artificial_lung": {
        "label": "Sztuczne Płuco (Artificial Lung)",
        "protocol": "Runtime Python Mapping",
        "cmd": {
          "lpm_5": "Ustaw 5 LPM",
          "lpm_10": "Ustaw 10 LPM",
          "lpm_15": "Ustaw 15 LPM",
          "lpm_20": "Ustaw 20 LPM",
          "lpm_30": "Ustaw 30 LPM",
          "lung_start": "Uruchom płuca",
          "lung_stop": "Zatrzymaj płuca",
          "lung_status": "Status płuca",
          "lung_cycle_3": "Cykl oddechowy (3x)",
          "lung_cycle_5": "Cykl oddechowy (5x)",
          "emergency_stop": "STOP AWARYJNY"
        }
      },
      "barcode_scanner": {
        "label": "Skaner kodów",
        "protocol": "USB HID / Keyboard Wedge",
        "cmd": {
          "scanner_status": "Sprawdź status skanera",
          "scanner_last": "Ostatni skan"
        }
      }
    },
    "presetStatusLine": "{label} · {protocol} · status: {status}",
    "running": "Wykonywanie…",
    "statusUnknown": "nieznany",
    "runtimeUnavailable": "Status runtime niedostępny",
    "proxyTarget": "Cel proxy",
    "commandResult": "Wynik polecenia",
    "copyCommandResult": "Kopiuj JSON wyniku",
    "runCommandHint": "Uruchom polecenie, aby zobaczyć wynik",
    "sidebarScanner": "Skaner kodów",
    "scanner": {
      "deviceStateTitle": "STAN URZĄDZENIA",
      "online": "Online",
      "offline": "Offline",
      "presentLabel": "Skaner obecny:",
      "yes": "Tak",
      "no": "Nie",
      "usbReported": "Zgłoszone USB:",
      "devicesCount": "{n} urządzeń",
      "driverMode": "Sterownik / tryb:",
      "lastReadTitle": "OSTATNI ODCZYT",
      "codeLabel": "Kod:",
      "typeLabel": "Typ:",
      "channelLabel": "Kanał:",
      "autoDetected": "Wykryty automatycznie",
      "noScans": "Brak zarejestrowanych skanów",
      "simulatorTitle": "SYMULATOR SKANERA LASEROWEGO (INGEST)",
      "codeInputLabel": "Zawartość kodu kreskowego / Link QR / UID",
      "symbologyLabel": "Format kodu (Symbologia)",
      "interfaceLabel": "Interfejs fizyczny",
      "codePlaceholder": "np. http://oqlos.lan/item-1234",
      "scanning": "Skanowanie...",
      "scanButton": "Skanuj laserem"
    }
  },
  "en": {
    "preset": {
      "modbus_io": {
        "label": "Waveshare Modbus RTU IO 8CH",
        "protocol": "Modbus RTU (RS485)",
        "cmd": {
          "valve_on_1": "Valve ON (valve-1)",
          "valve_off_1": "Valve OFF (valve-1)",
          "valve_on_2": "Valve ON (valve-2)",
          "valve_off_2": "Valve OFF (valve-2)",
          "read_all": "Read all valves",
          "status": "IO status"
        }
      },
      "motor_dri0050": {
        "label": "DFRobot DRI0050",
        "protocol": "MODBUS RTU (serial)",
        "cmd": {
          "pump_10": "Pump 10%",
          "pump_20": "Pump 20%",
          "pump_50": "Pump 50%",
          "pump_80": "Pump 80%",
          "pump_100": "Pump 100%",
          "pump_off": "Pump OFF",
          "status": "Pump status"
        }
      },
      "motor_tic249": {
        "label": "Pololu Tic T249",
        "protocol": "USB + REST",
        "cmd": {
          "lung_start_1": "Lung Start (1 cycle, 1000 steps/s)",
          "lung_start_3": "Lung Start (3 cycles, 1000 steps/s)",
          "lung_start_5": "Lung Start (5 cycles, 1000 steps/s)",
          "lung_stop": "Lung Stop",
          "motor_disable": "Motor Disable (de-energize)",
          "motor_enable": "Motor Enable",
          "status": "Motor status",
          "position": "Get position"
        }
      },
      "modbus_adc": {
        "label": "Waveshare Modbus RTU Analog Input 8CH",
        "protocol": "Modbus RTU (RS485)",
        "cmd": {
          "read_v1": "Read voltage V1",
          "read_v2": "Read voltage V2",
          "read_v3": "Read voltage V3",
          "read_v4": "Read voltage V4",
          "read_v5": "Read voltage V5",
          "read_v6": "Read voltage V6",
          "read_v7": "Read voltage V7",
          "read_v8": "Read voltage V8",
          "read_all": "Read all sensors",
          "status": "ADC status"
        }
      },
      "rtc": {
        "label": "Waveshare RTC WatchDog HAT (DS3231)",
        "protocol": "I2C (piRTC sidecar HTTP)",
        "cmd": {
          "read_status": "Read status",
          "read_time": "Read time",
          "read_date": "Read date",
          "read_temperature": "Read temperature",
          "read_watchdog": "Read watchdog status",
          "sync_to_system": "Sync RTC → system",
          "sync_from_system": "Sync system → RTC",
          "feed_watchdog": "Feed watchdog",
          "restart": "Restart (reinit hardware)"
        }
      },
      "artificial_lung": {
        "label": "Artificial Lung",
        "protocol": "Runtime Python Mapping",
        "cmd": {
          "lpm_5": "Set 5 LPM",
          "lpm_10": "Set 10 LPM",
          "lpm_15": "Set 15 LPM",
          "lpm_20": "Set 20 LPM",
          "lpm_30": "Set 30 LPM",
          "lung_start": "Start lungs",
          "lung_stop": "Stop lungs",
          "lung_status": "Lung status",
          "lung_cycle_3": "Breath cycle (3x)",
          "lung_cycle_5": "Breath cycle (5x)",
          "emergency_stop": "EMERGENCY STOP"
        }
      },
      "barcode_scanner": {
        "label": "Barcode scanner",
        "protocol": "USB HID / Keyboard Wedge",
        "cmd": {
          "scanner_status": "Check scanner status",
          "scanner_last": "Last scan"
        }
      }
    },
    "presetStatusLine": "{label} · {protocol} · status: {status}",
    "running": "Running...",
    "statusUnknown": "unknown",
    "runtimeUnavailable": "Runtime status unavailable",
    "proxyTarget": "Proxy Target",
    "commandResult": "Command Result",
    "copyCommandResult": "Copy command result JSON",
    "runCommandHint": "Run a command to see result",
    "sidebarScanner": "Barcode scanner",
    "scanner": {
      "deviceStateTitle": "DEVICE STATE",
      "online": "Online",
      "offline": "Offline",
      "presentLabel": "Scanner present:",
      "yes": "Yes",
      "no": "No",
      "usbReported": "USB reported:",
      "devicesCount": "{n} device(s)",
      "driverMode": "Driver / mode:",
      "lastReadTitle": "LAST READ",
      "codeLabel": "Code:",
      "typeLabel": "Type:",
      "channelLabel": "Channel:",
      "autoDetected": "Auto-detected",
      "noScans": "No scans recorded",
      "simulatorTitle": "LASER SCANNER SIMULATOR (INGEST)",
      "codeInputLabel": "Barcode content / QR link / UID",
      "symbologyLabel": "Symbology",
      "interfaceLabel": "Physical interface",
      "codePlaceholder": "e.g. http://oqlos.lan/item-1234",
      "scanning": "Scanning...",
      "scanButton": "Laser scan"
    }
  },
  "de": {
    "preset": {
      "modbus_io": {
        "label": "Waveshare Modbus RTU IO 8CH",
        "protocol": "Modbus RTU (RS485)",
        "cmd": {
          "valve_on_1": "Ventil EIN (valve-1)",
          "valve_off_1": "Ventil AUS (valve-1)",
          "valve_on_2": "Ventil EIN (valve-2)",
          "valve_off_2": "Ventil AUS (valve-2)",
          "read_all": "Alle Ventile lesen",
          "status": "IO-Status"
        }
      },
      "motor_dri0050": {
        "label": "DFRobot DRI0050",
        "protocol": "MODBUS RTU (seriell)",
        "cmd": {
          "pump_10": "Pumpe 10%",
          "pump_20": "Pumpe 20%",
          "pump_50": "Pumpe 50%",
          "pump_80": "Pumpe 80%",
          "pump_100": "Pumpe 100%",
          "pump_off": "Pumpe AUS",
          "status": "Pumpenstatus"
        }
      },
      "motor_tic249": {
        "label": "Pololu Tic T249",
        "protocol": "USB + REST",
        "cmd": {
          "lung_start_1": "Lunge Start (1 Zyklus)",
          "lung_start_3": "Lunge Start (3 Zyklen)",
          "lung_start_5": "Lunge Start (5 Zyklen)",
          "lung_stop": "Lunge Stop",
          "motor_disable": "Motor deaktivieren",
          "motor_enable": "Motor aktivieren",
          "status": "Motorstatus",
          "position": "Position lesen"
        }
      },
      "modbus_adc": {
        "label": "Waveshare Modbus RTU Analog 8CH",
        "protocol": "Modbus RTU (RS485)",
        "cmd": {
          "read_v1": "Spannung V1",
          "read_v2": "Spannung V2",
          "read_v3": "Spannung V3",
          "read_v4": "Spannung V4",
          "read_v5": "Spannung V5",
          "read_v6": "Spannung V6",
          "read_v7": "Spannung V7",
          "read_v8": "Spannung V8",
          "read_all": "Alle Sensoren lesen",
          "status": "ADC-Status"
        }
      },
      "rtc": {
        "label": "Waveshare RTC WatchDog HAT",
        "protocol": "I2C (piRTC sidecar HTTP)",
        "cmd": {
          "read_status": "Status lesen",
          "read_time": "Zeit lesen",
          "read_date": "Datum lesen",
          "read_temperature": "Temperatur",
          "read_watchdog": "Watchdog-Status",
          "sync_to_system": "RTC → System",
          "sync_from_system": "System → RTC",
          "feed_watchdog": "Watchdog füttern",
          "restart": "Neustart (HW)"
        }
      },
      "artificial_lung": {
        "label": "Künstliche Lunge",
        "protocol": "Runtime Python Mapping",
        "cmd": {
          "lpm_5": "5 LPM",
          "lpm_10": "10 LPM",
          "lpm_15": "15 LPM",
          "lpm_20": "20 LPM",
          "lpm_30": "30 LPM",
          "lung_start": "Lunge starten",
          "lung_stop": "Lunge stoppen",
          "lung_status": "Lungenstatus",
          "lung_cycle_3": "Atemzyklus (3x)",
          "lung_cycle_5": "Atemzyklus (5x)",
          "emergency_stop": "NOT-STOP"
        }
      },
      "barcode_scanner": {
        "label": "Barcode-Scanner",
        "protocol": "USB HID / Keyboard Wedge",
        "cmd": {
          "scanner_status": "Scannerstatus",
          "scanner_last": "Letzter Scan"
        }
      }
    },
    "presetStatusLine": "{label} · {protocol} · Status: {status}",
    "running": "Läuft…",
    "statusUnknown": "unbekannt",
    "runtimeUnavailable": "Runtime-Status nicht verfügbar",
    "proxyTarget": "Proxy-Ziel",
    "commandResult": "Befehlsergebnis",
    "copyCommandResult": "Befehls-JSON kopieren",
    "runCommandHint": "Befehl ausführen für Ergebnis",
    "sidebarScanner": "Barcode-Scanner",
    "scanner": {
      "deviceStateTitle": "GERÄTESTATUS",
      "online": "Online",
      "offline": "Offline",
      "presentLabel": "Scanner vorhanden:",
      "yes": "Ja",
      "no": "Nein",
      "usbReported": "USB gemeldet:",
      "devicesCount": "{n} Gerät(e)",
      "driverMode": "Treiber / Modus:",
      "lastReadTitle": "LETZTER SCAN",
      "codeLabel": "Code:",
      "typeLabel": "Typ:",
      "channelLabel": "Kanal:",
      "autoDetected": "Automatisch erkannt",
      "noScans": "Keine Scans",
      "simulatorTitle": "LASER-SCANNER-SIMULATOR (INGEST)",
      "codeInputLabel": "Barcode / QR / UID",
      "symbologyLabel": "Symbologie",
      "interfaceLabel": "Physische Schnittstelle",
      "codePlaceholder": "z. B. http://oqlos.lan/item-1234",
      "scanning": "Scanne…",
      "scanButton": "Laser-Scan"
    }
  },
  "ru": {
    "preset": {
      "modbus_io": {
        "label": "Waveshare Modbus RTU IO 8CH",
        "protocol": "Modbus RTU (RS485)",
        "cmd": {
          "valve_on_1": "Клапан ВКЛ (valve-1)",
          "valve_off_1": "Клапан ВЫКЛ (valve-1)",
          "valve_on_2": "Клапан ВКЛ (valve-2)",
          "valve_off_2": "Клапан ВЫКЛ (valve-2)",
          "read_all": "Читать все клапаны",
          "status": "Статус IO"
        }
      },
      "motor_dri0050": {
        "label": "DFRobot DRI0050",
        "protocol": "MODBUS RTU (последовательный)",
        "cmd": {
          "pump_10": "Насос 10%",
          "pump_20": "Насос 20%",
          "pump_50": "Насос 50%",
          "pump_80": "Насос 80%",
          "pump_100": "Насос 100%",
          "pump_off": "Насос ВЫКЛ",
          "status": "Статус насоса"
        }
      },
      "motor_tic249": {
        "label": "Pololu Tic T249",
        "protocol": "USB + REST",
        "cmd": {
          "lung_start_1": "Старт лёгких (1 цикл)",
          "lung_start_3": "Старт лёгких (3 цикла)",
          "lung_start_5": "Старт лёгких (5 циклов)",
          "lung_stop": "Стоп лёгких",
          "motor_disable": "Отключить мотор",
          "motor_enable": "Включить мотор",
          "status": "Статус мотора",
          "position": "Позиция"
        }
      },
      "modbus_adc": {
        "label": "Waveshare Modbus RTU АЦП 8CH",
        "protocol": "Modbus RTU (RS485)",
        "cmd": {
          "read_v1": "Напряжение V1",
          "read_v2": "Напряжение V2",
          "read_v3": "Напряжение V3",
          "read_v4": "Напряжение V4",
          "read_v5": "Напряжение V5",
          "read_v6": "Напряжение V6",
          "read_v7": "Напряжение V7",
          "read_v8": "Напряжение V8",
          "read_all": "Все датчики",
          "status": "Статус АЦП"
        }
      },
      "rtc": {
        "label": "Waveshare RTC WatchDog HAT",
        "protocol": "I2C (piRTC sidecar HTTP)",
        "cmd": {
          "read_status": "Статус",
          "read_time": "Время",
          "read_date": "Дата",
          "read_temperature": "Температура",
          "read_watchdog": "Watchdog",
          "sync_to_system": "RTC → система",
          "sync_from_system": "система → RTC",
          "feed_watchdog": "Сброс watchdog",
          "restart": "Перезапуск"
        }
      },
      "artificial_lung": {
        "label": "Искусственное лёгкое",
        "protocol": "Runtime Python Mapping",
        "cmd": {
          "lpm_5": "5 LPM",
          "lpm_10": "10 LPM",
          "lpm_15": "15 LPM",
          "lpm_20": "20 LPM",
          "lpm_30": "30 LPM",
          "lung_start": "Запуск лёгких",
          "lung_stop": "Стоп лёгких",
          "lung_status": "Статус лёгких",
          "lung_cycle_3": "Цикл (3x)",
          "lung_cycle_5": "Цикл (5x)",
          "emergency_stop": "АВАРИЙНЫЙ СТОП"
        }
      },
      "barcode_scanner": {
        "label": "Сканер штрихкодов",
        "protocol": "USB HID / Keyboard Wedge",
        "cmd": {
          "scanner_status": "Статус сканера",
          "scanner_last": "Последний скан"
        }
      }
    },
    "presetStatusLine": "{label} · {protocol} · статус: {status}",
    "running": "Выполнение…",
    "statusUnknown": "неизвестно",
    "runtimeUnavailable": "Статус runtime недоступен",
    "proxyTarget": "Цель proxy",
    "commandResult": "Результат команды",
    "copyCommandResult": "Копировать JSON результата",
    "runCommandHint": "Запустите команду для результата",
    "sidebarScanner": "Сканер",
    "scanner": {
      "deviceStateTitle": "СОСТОЯНИЕ",
      "online": "Online",
      "offline": "Offline",
      "presentLabel": "Сканер:",
      "yes": "Да",
      "no": "Нет",
      "usbReported": "USB:",
      "devicesCount": "{n} устройств",
      "driverMode": "Драйвер / режим:",
      "lastReadTitle": "ПОСЛЕДНИЙ СКАН",
      "codeLabel": "Код:",
      "typeLabel": "Тип:",
      "channelLabel": "Канал:",
      "autoDetected": "Автоопределение",
      "noScans": "Нет сканов",
      "simulatorTitle": "СИМУЛЯТОР СКАНЕРА (INGEST)",
      "codeInputLabel": "Штрихкод / QR / UID",
      "symbologyLabel": "Символология",
      "interfaceLabel": "Интерфейс",
      "codePlaceholder": "напр. http://oqlos.lan/item-1234",
      "scanning": "Сканирование…",
      "scanButton": "Сканировать"
    }
  },
  "ua": {
    "preset": {
      "modbus_io": {
        "label": "Waveshare Modbus RTU IO 8CH",
        "protocol": "Modbus RTU (RS485)",
        "cmd": {
          "valve_on_1": "Клапан УВІМК (valve-1)",
          "valve_off_1": "Клапан ВИМК (valve-1)",
          "valve_on_2": "Клапан УВІМК (valve-2)",
          "valve_off_2": "Клапан ВИМК (valve-2)",
          "read_all": "Читати всі клапани",
          "status": "Статус IO"
        }
      },
      "motor_dri0050": {
        "label": "DFRobot DRI0050",
        "protocol": "MODBUS RTU (послідовний)",
        "cmd": {
          "pump_10": "Насос 10%",
          "pump_20": "Насос 20%",
          "pump_50": "Насос 50%",
          "pump_80": "Насос 80%",
          "pump_100": "Насос 100%",
          "pump_off": "Насос ВИМК",
          "status": "Статус насоса"
        }
      },
      "motor_tic249": {
        "label": "Pololu Tic T249",
        "protocol": "USB + REST",
        "cmd": {
          "lung_start_1": "Старт легенів (1 цикл)",
          "lung_start_3": "Старт легенів (3 цикли)",
          "lung_start_5": "Старт легенів (5 циклів)",
          "lung_stop": "Стоп легенів",
          "motor_disable": "Вимкнути мотор",
          "motor_enable": "Увімкнути мотор",
          "status": "Статус мотора",
          "position": "Позиція"
        }
      },
      "modbus_adc": {
        "label": "Waveshare Modbus RTU АЦП 8CH",
        "protocol": "Modbus RTU (RS485)",
        "cmd": {
          "read_v1": "Напруга V1",
          "read_v2": "Напруга V2",
          "read_v3": "Напруга V3",
          "read_v4": "Напруга V4",
          "read_v5": "Напруга V5",
          "read_v6": "Напруга V6",
          "read_v7": "Напруга V7",
          "read_v8": "Напруга V8",
          "read_all": "Всі датчики",
          "status": "Статус АЦП"
        }
      },
      "rtc": {
        "label": "Waveshare RTC WatchDog HAT",
        "protocol": "I2C (piRTC sidecar HTTP)",
        "cmd": {
          "read_status": "Статус",
          "read_time": "Час",
          "read_date": "Дата",
          "read_temperature": "Температура",
          "read_watchdog": "Watchdog",
          "sync_to_system": "RTC → система",
          "sync_from_system": "система → RTC",
          "feed_watchdog": "Скинути watchdog",
          "restart": "Перезапуск"
        }
      },
      "artificial_lung": {
        "label": "Штучне легене",
        "protocol": "Runtime Python Mapping",
        "cmd": {
          "lpm_5": "5 LPM",
          "lpm_10": "10 LPM",
          "lpm_15": "15 LPM",
          "lpm_20": "20 LPM",
          "lpm_30": "30 LPM",
          "lung_start": "Запуск легенів",
          "lung_stop": "Стоп легенів",
          "lung_status": "Статус легенів",
          "lung_cycle_3": "Цикл (3x)",
          "lung_cycle_5": "Цикл (5x)",
          "emergency_stop": "АВАРІЙНА ЗУПИНКА"
        }
      },
      "barcode_scanner": {
        "label": "Сканер штрихкодів",
        "protocol": "USB HID / Keyboard Wedge",
        "cmd": {
          "scanner_status": "Статус сканера",
          "scanner_last": "Останній скан"
        }
      }
    },
    "presetStatusLine": "{label} · {protocol} · статус: {status}",
    "running": "Виконання…",
    "statusUnknown": "невідомо",
    "runtimeUnavailable": "Статус runtime недоступний",
    "proxyTarget": "Ціль proxy",
    "commandResult": "Результат команди",
    "copyCommandResult": "Копіювати JSON результату",
    "runCommandHint": "Запустіть команду для результату",
    "sidebarScanner": "Сканер",
    "scanner": {
      "deviceStateTitle": "СТАН ПРИСТРОЮ",
      "online": "Online",
      "offline": "Offline",
      "presentLabel": "Сканер:",
      "yes": "Так",
      "no": "Ні",
      "usbReported": "USB:",
      "devicesCount": "{n} пристроїв",
      "driverMode": "Драйвер / режим:",
      "lastReadTitle": "ОСТАННІЙ СКАН",
      "codeLabel": "Код:",
      "typeLabel": "Тип:",
      "channelLabel": "Канал:",
      "autoDetected": "Автовизначення",
      "noScans": "Немає сканів",
      "simulatorTitle": "СИМУЛЯТОР СКАНЕРА (INGEST)",
      "codeInputLabel": "Штрихкод / QR / UID",
      "symbologyLabel": "Символологія",
      "interfaceLabel": "Інтерфейс",
      "codePlaceholder": "напр. http://oqlos.lan/item-1234",
      "scanning": "Сканування…",
      "scanButton": "Сканувати"
    }
  },
  "cs": {
    "preset": {
      "modbus_io": {
        "label": "Waveshare Modbus RTU IO 8CH",
        "protocol": "Modbus RTU (RS485)",
        "cmd": {
          "valve_on_1": "Ventil ON (valve-1)",
          "valve_off_1": "Ventil OFF (valve-1)",
          "valve_on_2": "Ventil ON (valve-2)",
          "valve_off_2": "Ventil OFF (valve-2)",
          "read_all": "Číst všechny ventily",
          "status": "Stav IO"
        }
      },
      "motor_dri0050": {
        "label": "DFRobot DRI0050",
        "protocol": "MODBUS RTU (sériový)",
        "cmd": {
          "pump_10": "Čerpadlo 10%",
          "pump_20": "Čerpadlo 20%",
          "pump_50": "Čerpadlo 50%",
          "pump_80": "Čerpadlo 80%",
          "pump_100": "Čerpadlo 100%",
          "pump_off": "Čerpadlo OFF",
          "status": "Stav čerpadla"
        }
      },
      "motor_tic249": {
        "label": "Pololu Tic T249",
        "protocol": "USB + REST",
        "cmd": {
          "lung_start_1": "Plíce start (1 cyklus)",
          "lung_start_3": "Plíce start (3 cykly)",
          "lung_start_5": "Plíce start (5 cyklů)",
          "lung_stop": "Plíce stop",
          "motor_disable": "Motor vypnout",
          "motor_enable": "Motor zapnout",
          "status": "Stav motoru",
          "position": "Pozice"
        }
      },
      "modbus_adc": {
        "label": "Waveshare Modbus RTU Analog 8CH",
        "protocol": "Modbus RTU (RS485)",
        "cmd": {
          "read_v1": "Napětí V1",
          "read_v2": "Napětí V2",
          "read_v3": "Napětí V3",
          "read_v4": "Napětí V4",
          "read_v5": "Napětí V5",
          "read_v6": "Napětí V6",
          "read_v7": "Napětí V7",
          "read_v8": "Napětí V8",
          "read_all": "Všechny senzory",
          "status": "Stav ADC"
        }
      },
      "rtc": {
        "label": "Waveshare RTC WatchDog HAT",
        "protocol": "I2C (piRTC sidecar HTTP)",
        "cmd": {
          "read_status": "Stav",
          "read_time": "Čas",
          "read_date": "Datum",
          "read_temperature": "Teplota",
          "read_watchdog": "Watchdog",
          "sync_to_system": "RTC → systém",
          "sync_from_system": "systém → RTC",
          "feed_watchdog": "Nakrmit watchdog",
          "restart": "Restart (HW)"
        }
      },
      "artificial_lung": {
        "label": "Umělá plíce",
        "protocol": "Runtime Python Mapping",
        "cmd": {
          "lpm_5": "5 LPM",
          "lpm_10": "10 LPM",
          "lpm_15": "15 LPM",
          "lpm_20": "20 LPM",
          "lpm_30": "30 LPM",
          "lung_start": "Spustit plíce",
          "lung_stop": "Zastavit plíce",
          "lung_status": "Stav plic",
          "lung_cycle_3": "Cykl (3x)",
          "lung_cycle_5": "Cykl (5x)",
          "emergency_stop": "NOUZOVÝ STOP"
        }
      },
      "barcode_scanner": {
        "label": "Čtečka čárových kódů",
        "protocol": "USB HID / Keyboard Wedge",
        "cmd": {
          "scanner_status": "Stav skeneru",
          "scanner_last": "Poslední sken"
        }
      }
    },
    "presetStatusLine": "{label} · {protocol} · stav: {status}",
    "running": "Probíhá…",
    "statusUnknown": "neznámý",
    "runtimeUnavailable": "Runtime stav nedostupný",
    "proxyTarget": "Proxy cíl",
    "commandResult": "Výsledek příkazu",
    "copyCommandResult": "Kopírovat JSON výsledku",
    "runCommandHint": "Spusťte příkaz pro výsledek",
    "sidebarScanner": "Skener",
    "scanner": {
      "deviceStateTitle": "STAV ZAŘÍZENÍ",
      "online": "Online",
      "offline": "Offline",
      "presentLabel": "Skener:",
      "yes": "Ano",
      "no": "Ne",
      "usbReported": "USB:",
      "devicesCount": "{n} zařízení",
      "driverMode": "Ovladač / režim:",
      "lastReadTitle": "POSLEDNÍ SKEN",
      "codeLabel": "Kód:",
      "typeLabel": "Typ:",
      "channelLabel": "Kanál:",
      "autoDetected": "Automaticky detekováno",
      "noScans": "Žádné skeny",
      "simulatorTitle": "SIMULÁTOR SKENERU (INGEST)",
      "codeInputLabel": "Čárový kód / QR / UID",
      "symbologyLabel": "Symbologie",
      "interfaceLabel": "Fyzické rozhraní",
      "codePlaceholder": "např. http://oqlos.lan/item-1234",
      "scanning": "Skenování…",
      "scanButton": "Skenovat"
    }
  }
};
