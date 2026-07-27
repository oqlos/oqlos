# OqlOS BoardNet — zapis stanu i aktualna architektura

Ostatnio sprawdzono: 2026-07-24 Europe/Warsaw.

## Aktualizacja 2026-07-24

- Ostatni deploy z `redeploy` 0.2.80 ponownie przeszedł **25/25**, checksumy
  **206/206** i firmware smoke **1/1**; brak failed units.
- Kanoniczny deploy `redeploy/122/migration.md`: **25/25** kroków.
- Manifest integralności: **206** zweryfikowanych sum SHA-256.
- Firmware smoke TestQL: **1/1**.
- Health: `mode=real`, `overall_ok=true`, `degraded=false`;
  podłączone `motor-dri0050`, `motor-tic249`, `modbus-io`, zero failed.
- `modbus-adc` pozostaje świadomie wyłączony, ponieważ wejścia analogowe
  obsługuje `usb-adc-stack`.
- `dri0050`, `tic249`, `pirtc`, OqlOS i MQTT są aktywne; brak failed units.
- Po końcowym audycie DRI0050 został zatrzymany i trzy odczyty potwierdziły
  `enabled=false`, `duty=0`.

## UI BoardNet (kanoniczne URL)

| URL | Lewy panel | Górne menu |
| --- | --- | --- |
| `http://192.168.188.122:8202/ui/scenario-files` | Lista plików `.oql` + wyszukiwarka | OqlOS, Status, Restart, Demo, Scenariusze, Funkcje, Silniki, OQL, Nawigacja, API |
| `http://localhost:8100/connect-oql-system` | Edytor `hardware-configuration-v1` w OQL/YAML/JSON | Konfiguracja, walidacja, konwersja i zapis bez aktywacji wyjść |

Legacy `/map`, `/map-editor` i `/ui/map-editor` są wycofane i zwracają 404.
`/scenario-files` nadal przekierowuje na kanoniczny widok `/ui/scenario-files`.
Pełna tabela: `docs/boardnet-navigation.md`.

## HUI Ctrl+Alt+1…9 (mapowanie)

Katalog: `GET http://192.168.188.122:8202/api/v1/hardware/hui/actions`

| Skrót | Klucz | Profil (skrót) |
| --- | --- | --- |
| Ctrl+Alt+1 | `head-deflate` | valve-3, valve-6, pump 0% |
| Ctrl+Alt+2 | `lp-pwm-plus5` | valve-5, pump 50% |
| Ctrl+Alt+3 | `lp-pwm-plus10` | valve-5, pump 100% |
| Ctrl+Alt+4 | `al-start` | płuco L→R (`reverse_on_limit`) |
| Ctrl+Alt+5 | `lp-bleed` | valve-4, pump 0% |
| Ctrl+Alt+6 | `head-inflate` | valve-5, valve-2, pump 70% |
| Ctrl+Alt+7 | `lp-pwm-minus5` | valve-6, pump 50% |
| Ctrl+Alt+8 | `lp-pwm-minus10` | valve-6, pump 100% |
| Ctrl+Alt+9 | `al-stop` | stop płuca |

**2026-07-07:** katalog `ok=true`, wszystkie 9 kluczy obecne. Wykonanie na benchu
bywa **degraded**: `modbus-io` timeout → `POST .../hold/lp-pwm-minus10/start`
zwraca `Valve valve-6 failed`; `al/stop` kończy `stop_lung` OK, ale
`set_valve valve-4` może być `ok=false`. Mapowanie logiczne jest poprawne;
naprawa wymaga stabilnego RS485 (slave ID 2, patrz sekcja „Ostatnia naprawa”).

DisplayNet (`:8100`) używa tego samego API przez proxy:
`/api/v3/hardware/hui/*` → `http://192.168.188.122:8202/api/v1/hardware/hui/*`.

## Rola

- **BoardNet / RPi3**: `pi@192.168.188.122`
  - Hostname systemowy: `boardnet.local`.
  - Właściciel produkcyjnego OqlOS firmware i bezpośrednio podłączonego hardware.
  - OqlOS API/UI: `:8202`; DRI0050: `:8203`; Tic249: `:8205`; piRTC: `:8125`.
  - Strefa czasu: `Europe/Warsaw`; piRTC DS3231 zsynchronizowany z czasem systemowym BoardNet.
- **DisplayNet / RPi5**: `pi@192.168.188.109`
  - Hostname systemowy: `displaynet`.
  - Właściciel GUI/kiosku/orchestracji c2004.
  - Do BoardNet idzie przez `OQLOS_API_URL=http://192.168.188.122:8202`.

## Ścieżka sterowania

```text
Browser/HUI on DisplayNet :8100
  -> /api/v3/hardware/hui/* + diagnostic-command on c2004/connect-scenario backend
  -> OQLOS_API_URL=http://192.168.188.122:8202
  -> OqlOS on BoardNet (/api/v1/hardware/hui/*)
  -> local USB/Modbus/Tic/DRI hardware on BoardNet
```

MQTT nadal działa lokalnie na BoardNet (`mosquitto :1883`, node_id `boardnet`)
dla ścieżki OQL-over-MQTT, ale aktualna ścieżka GUI c2004 używa bezpośredniego
HTTP do `:8202`.

## Zweryfikowane komendy

```bash
ssh pi@192.168.188.122 'hostname; tr -d "\0" </proc/device-tree/model; echo'
ssh pi@192.168.188.122 'systemctl --user is-active oqlos-hardware-api hw-tic249 dri0050-motor-api mosquitto pirtc-api'
curl -s http://192.168.188.122:8202/api/v1/hardware/health
curl -s http://192.168.188.122:8202/api/v1/hardware/hui/actions
curl -s http://192.168.188.122:8125/api/status
curl -s http://192.168.188.122:8202/api/v1/hardware/rtc/status
curl -s http://192.168.188.122:8205/api/status
curl -s http://192.168.188.122:8203/health
```

## Zdrowe elementy

- `oqlos-hardware-api.service`, `hw-tic249.service`,
  `dri0050-motor-api.service`, `mosquitto.service` i `pirtc-api.service` są
  aktywne.
- piRTC WatchDog HAT jest rozpoznany realnie na BoardNet:
  - `/dev/i2c-1` i `/dev/i2c-2` są obecne,
  - `http://192.168.188.122:8125/api/status` zwraca `rtc.available=true`,
    `watchdog.available=true`, `mock=false`,
  - `http://192.168.188.122:8202/api/v1/hardware/rtc/status` zwraca
    `connected=true`, `ready=true`, `mock=false`,
  - po reboot BoardNet `.122` piRTC wrócił jako `active` i nadal zwraca
    `rtc.available=true`, `watchdog.available=true`, `mock=false`,
  - ostatni sprawdzony czas DS3231: `2026-06-30 22:02 Europe/Warsaw`.
- Po reboot BoardNet `.122` wszystkie powyższe usługi wróciły jako `active`,
  porty `1883`, `8125`, `8202`, `8203`, `8205` słuchały, a
  `systemctl --user --failed` był pusty.
- USB widoczne na BoardNet:
  - Pololu Tic T249: `1ffb:00c9`
  - MCP2221A USB-I2C/UART: `/dev/ttyACM0` (AI01 przez usb-adc-stack)
  - CH340 USB2.0-Serial: `/dev/ttyUSB0` (DRI0050)
  - FTDI FT232R: `/dev/ttyUSB1` (adapter widoczny, brak odpowiedzi RTU)
  - DFR1184 używa UART Raspberry Pi `/dev/serial0` (AI02/AI03), nie USB.
- Tic249 raportuje `connected=true`, `energized=false`.
- DRI0050 raportuje zdrowy stan na `:8203`.
- Modbus-IO jest podłączony na slave ID `2` i raportuje `status=connected`,
  `compatible=true`.
- OqlOS działa w `mode=real`; ostatni health ma `overall_ok=true`,
  `degraded=false`, trzy podłączone pluginy i zero failed.
- HTTP HUI: `GET /api/v1/hardware/hui/actions` zwraca katalog hold/AL;
  bezpieczne `POST /api/v1/hardware/hui/al/stop` i `shutdown` weryfikuje
  `assert_hw_node_healthy` w `redeploy/122/migration.md`.
- `modbus-adc` jest świadomie wyłączony (`enabled=false`, `status=disabled`),
  ponieważ AI01–AI03 obsługuje usb-adc-stack (MCP2221A + DFR1184).

## Migracja wejść analogowych 2026-07-22

- `ai01` odpowiada przez `usb-adc-mcp2221`, fizycznie `MCP2221A.G1`.
- `ai02` i `ai03` odpowiadają przez `usb-adc-dfr1184`, odpowiednio
  `DFR1184.AIN1` i `DFR1184.AIN2`, transport UART `/dev/serial0`.
- Publiczny proxy DisplayNet `/firmware/api/v1/hardware/sensors/batch` zwraca
  wszystkie kanały z `ok=true`; ostatni odczyt bez podanego sygnału wynosił
  `0.0 V`.
- Autodetekcja Modbus pomija MCP2221 i port pompy DRI0050. Nie próbuje już
  uruchamiać starego `modbus-adc` ani raportować go jako źródła analogowego.

## Ostatnia historyczna naprawa Modbus-IO (2026-07-07)

- Aktualna polityka runtime dla Waveshare Modbus-IO to
  `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5958006895-if00`,
  `4800/N/8/1`, slave ID `2`.
- Nie programowano modułu i nie wykonywano `repair --yes`.
- Poprawiono konfigurację runtime na `modbus-io.device_id=2` oraz
  `OQLOS_MODBUS_DEVICE_ID=2`.
- `redeploy/122/migration.md` wykrywa teraz slave ID dla `modbus-io`, więc
  ponowny deploy nie powinien cofnąć ustawienia do ID `1`.

## Wykonana diagnostyka read-only

- Zatrzymano tylko `oqlos-hardware-api.service`, sidecary zostawiono aktywne,
  potem firmware został ponownie uruchomiony.
- Krótki skan targetowany powinien używać (`4800`, parity `N`, IDs `1,2`)
  i oczekiwać odpowiedzi
  `read_coils` dla ID `2`.
- Po restarcie OqlOS: `modbus-io` jest healthy, Tic249 nadal
  `energized=false`.
- Po reboot BoardNet: Tic249 nadal `energized=false`.
- Po reboot DisplayNet `.109`: proxy c2004 nadal czyta BoardNet piRTC po
  `http://192.168.188.122:8125`, a RTC w `/api/v3/hardware/identify` ma
  `status=ok`, `mock=false`.

Powiązany snapshot po stronie c2004:
`/home/tom/github/maskservice/c2004/redeploy/pi109/CURRENT_STATE.md`.
