# Sterowanie sprzętem przez OQL-over-MQTT + Panel testowy

Dokumentacja warstwy sterowania sprzętem OqlOS na **dedykowanym węźle sprzętowym**
(Raspberry Pi) przez komendy **OQL wysyłane po MQTT**, oraz **Panelu testowego**.

- **Architektura**: aplikacja (np. connect-scenario) → *controller* OqlOS (HTTP) →
  broker MQTT → *agent* OqlOS na Pi → realny sprzęt → odpowiedź tą samą drogą.
- HTTP `:8202` agenta na Pi jest tylko **loopback**; jedyny transport między węzłami to MQTT.
- Referencyjny węzeł: **boardnet = `pi@192.168.188.122`** (Raspberry Pi 3), node_id `boardnet`,
  prefiks tematów `oqlos/c2004`.

---

## 0. Granica: gdzie żyje sprzęt (firmware-sim vs oqlos)

Zasada: **sterowniki fizyczne sprzętu są w oqlos i sidecarach, NIE w kodzie aplikacji c2004.**
Zweryfikowane audytem — w kodzie aplikacji c2004 nie ma `pyusb`/`ticlib`/`pymodbus`/`RPi.GPIO`/
`smbus`; c2004 rozmawia ze sprzętem wyłącznie przez oqlos (HTTP proxy `:8202` + OQL-over-MQTT).

API firmware na **`:8202`** ma DWA źródła zależnie od środowiska — to celowe, nie duplikat:

| Środowisko | Dostawca `:8202` | Uwaga |
|-----------|------------------|-------|
| **Docker** (dev/prod/vps) | usługa `c2004-firmware` (`backend/firmware/`) — symulator/mock | routowana przez Traefik (`/firmware`), używana przez frontend (`VITE_FIRMWARE_URL`) |
| **Realny sprzęt** (pi109) | `oqlos-hardware-api` (host systemd) | `c2004-firmware` jest **zamaskowany**; oqlos przejmuje `:8202` |
| **Dedykowany węzeł sprzętowy** (boardnet) | `oqlos` rola `agent` (`:8202` loopback) | transport do niego = **MQTT**, nie HTTP |

Czyli: **firmware-sim = backend `:8202` dla docker/dev/prod**; **oqlos = `:8202` na realnym sprzęcie**.
`backend/firmware/` NIE jest legacy do usunięcia — to aktywny, produkcyjny (Traefik) backend docker.

W c2004 pozostała tylko **diagnostyka host-coupled** (analiza `serial_ports` z oqlos, host
`make`/`systemctl`) — nie otwiera urządzeń. Legacy bridge'y skanera/modbus/rtc zostały usunięte
(zastąpione przez `oqlos.hardware.scanner_probe` / `modbus_identify` / `rtc_probe`).

---

## 1. Architektura i role

```
aplikacja / przeglądarka
        │ HTTP  POST /api/v1/oql/{execute,manage}  ·  WS /ws/oql  ·  GET /panel
        ▼
OqlOS  role=controller   (most HTTP → MQTT)
        │ MQTT (publish request / subscribe response)
        ▼
broker MQTT  (:1883)      mosquitto (prod) lub amqtt (dev)
        ▼
OqlOS  role=agent  na Pi  (HARDWARE_MODE=real)
        │ wykonuje OQL / verb na PluginHardwareGateway
        ▼
realny sprzęt (Modbus IO/ADC, Pololu Tic T249, DRI0050, RTC, USB…)
```

Rola ustawiana przez `OQLOS_OQL_TRANSPORT_ROLE`:

| Rola | Gdzie działa | Zachowanie |
|------|--------------|------------|
| `off` (domyślnie) | — | brak transportu MQTT (zachowuje tryb jednoprocesowy) |
| `controller` | węzeł aplikacyjny (pi109 / dev) | publikuje OQL, czeka na odpowiedź; serwuje `/api/v1/oql/*` |
| `agent` | węzeł sprzętowy (boardnet) | subskrybuje żądania, wykonuje OQL na lokalnym sprzęcie, odpowiada |
| `both` | dev / loopback | controller + agent na jednym brokerze (testy) |

### Schemat tematów MQTT (prefiks domyślnie `oqlos/c2004`, per-węzeł `node_id`)
```
<prefix>/<node_id>/oql/request          controller → agent   QoS 1
<prefix>/<node_id>/oql/response/<corr>  agent → controller   QoS 1
<prefix>/<node_id>/oql/events           agent → wszyscy      QoS 0
<prefix>/<node_id>/oql/status           agent → wszyscy      QoS 1 retained (last-will)
```

---

## 2. Uruchomienie (kolejność ma znaczenie)

Na czystym starcie **zawsze** w kolejności **broker → agent → controller** (agent musi
najpierw zasubskrybować temat żądań):

```bash
# 1) Broker na węźle sprzętowym (prod: mosquitto; dev bez sudo: amqtt)
amqtt -c ~/maskservice/config/amqtt.yaml          # dev (pip install amqtt)
#   systemctl --user start mosquitto               # prod (redeploy/122)

# 2) Agent na Pi (HTTP loopback, agent MQTT)
OQLOS_HARDWARE_MODE=real \
OQLOS_OQL_TRANSPORT_ROLE=agent OQLOS_OQL_NODE_ID=boardnet \
OQLOS_OQL_MQTT_HOST=127.0.0.1 OQLOS_OQL_MQTT_PORT=1883 \
oqlos-server --host 0.0.0.0 --port 8202
#   poczekaj na log: "OqlMqttAgent connected (node=boardnet)"

# 3) Controller na węźle aplikacyjnym (most HTTP→MQTT)
OQLOS_OQL_TRANSPORT_ROLE=controller OQLOS_OQL_NODE_ID=boardnet \
OQLOS_OQL_MQTT_HOST=192.168.188.122 OQLOS_OQL_MQTT_PORT=1883 \
OQLOS_HARDWARE_MODE=mock \
oqlos-server --host 0.0.0.0 --port 8210
```

### Skrypt zarządzający stosem (dev, bez sudo)

Zamiast ręcznie odpalać trzy procesy, użyj `scripts/oql-stack.sh` — uruchamia/zatrzymuje
broker + agent (+ opcjonalny sidecar Tic) na Pi oraz controller lokalnie, w poprawnej kolejności:

```bash
scripts/oql-stack.sh up       # broker → agent → sidecar → controller (z health-checkami)
scripts/oql-stack.sh status   # stan wszystkich elementów + status węzła przez MQTT
scripts/oql-stack.sh panel    # wypisuje URL panelu (http://<ip>:8210/panel)
scripts/oql-stack.sh down     # zatrzymuje wszystko
```

Konfiguracja przez env: `OQL_PI` (domyślnie `pi@boardnet.local`), `OQL_NODE` (`boardnet`),
`OQL_BROKER_LAN` (`192.168.188.122`), `OQL_SERIAL` (`/dev/ttyUSB0`), `OQL_CTRL_PORT` (`8210`),
`OQL_CTRL_HOST` (`0.0.0.0` = dostęp z LAN). To tryb **dev** (broker `amqtt`); produkcja używa
`mosquitto` + systemd przez `redeploy/122`.

### Zmienne środowiskowe (`oqlos/config.py`)
| Zmienna | Domyślnie | Opis |
|---------|-----------|------|
| `OQLOS_OQL_TRANSPORT_ROLE` | `off` | off \| controller \| agent \| both |
| `OQLOS_OQL_NODE_ID` | `default` | identyfikator węzła sprzętowego |
| `OQLOS_OQL_MQTT_HOST` | `localhost` | host brokera |
| `OQLOS_OQL_MQTT_PORT` | `1883` | port brokera |
| `OQLOS_OQL_MQTT_USERNAME` / `_PASSWORD` | `""` | uwierzytelnianie brokera (prod) |
| `OQLOS_OQL_TOPIC_PREFIX` | `oqlos/c2004` | prefiks tematów |
| `OQLOS_OQL_TIMEOUT_MS` | `15000` | domyślny timeout odpowiedzi |

connect-scenario (klient): `HARDWARE_TRANSPORT=mqtt` + `OQLOS_OQL_CONTROLLER_URL=http://127.0.0.1:8202`
przełącza dyspatcher CQRS na ścieżkę OQL-over-MQTT (przez lokalny controller).

---

## 3. Panel testowy (dashboard)

Serwowany przez instancję **controller** (lub każdą instancję OqlOS) pod **`/panel`**;
strona startowa z linkami pod **`/`**.

- LAN: `http://<host-controllera>:8210/panel` (np. `http://192.168.188.212:8210/panel`)
- Aby był dostępny z innych urządzeń, controller musi nasłuchiwać na `--host 0.0.0.0`.

Funkcje:
- **Predefiniowane grupy komend** (klik = wykonanie; **▶ grupa** = uruchom całą grupę po kolei):
  Diagnostyka, Zawory, Pompa, Płuco (Tic T249), Sensory (ADC), Diagnostyka RPi3 / USB.
- **Edytor scenariuszy OQL** z trybem **Wykonaj / Symulacja / Walidacja** (wysyła jako
  `kind=script` przez `/api/v1/oql/execute`).
- **Scenariusze**: szablony wbudowane + **[moje]** (zapis/usuwanie w przeglądarce, localStorage)
  + **[serwer]** (`/api/v1/scenarios/fetch`). Zapis: `💾 Zapisz bieżący` / usuwanie: `🗑 Usuń wybrany`.
- **Monitor na żywo**: wykres (sparkline) wybranej metryki — temperatura CPU (`pi-diagnostics`)
  lub sensor — odpytywany co N sekund.
- **Wyniki**: każdy wpis pokazuje **`→ wysłano`** (dokładny request) i **`← odebrano`** (dane),
  plus pełny JSON; przyciski **📋** (kopiuj komendę/JSON), **↻ powtórz** (replay).
- **Kolory statusu**: 🟢 OK · 🟡 N/D (sprzęt niedostępny / brak uprawnień — także gdy
  `result.success/ok=false`) · 🔴 BŁĄD.
- **Eksport**: `📋 Kopiuj wszystko`, `⬇ JSON`, `⬇ CSV`. **Auto-refresh** statusu (10 s).
  **Filtr** wyników (po tytule / komendzie / odpowiedzi). **🌓 motyw** jasny/ciemny (zapamiętany).
- **Skróty**: `Ctrl+Enter` uruchom · `Ctrl+S` zapisz scenariusz · `/` filtr · `Esc` wyczyść filtr.
- Nagłówek pokazuje status węzła (`node_id` + `mode`).

Jeśli panel działa na instancji bez roli controller, `/api/v1/oql/*` zwróci **503** i panel
pokaże baner — uruchom OqlOS w roli controller.

Pliki: `oqlos/api/static/panel.html`, `oqlos/api/index.html` (route `/panel`, `/` w `oqlos/api/main.py`).

### Integracja z connect-scenario (zweryfikowana)
`connect-scenario` działa na obu transportach:
- **HTTP proxy** (`OQLOS_API_URL=http://<hw-pi>:8202`) — `/api/v3/hardware/*` → węzeł, `mode=real`.
- **OQL-over-MQTT** (`HARDWARE_TRANSPORT=mqtt`, `OQLOS_OQL_CONTROLLER_URL=http://127.0.0.1:8202`):
  `POST /api/v3/hardware/cqrs/command` → lokalny controller → MQTT → agent → realny sprzęt;
  odpowiedź ma `transport: "mqtt"`, zdarzenie CQRS jest zapisywane.

---

## 4. API OQL-over-MQTT

### `POST /api/v1/oql/execute`
Wykonuje OQL na zdalnym węźle.
```json
{ "oql": "SET 'valve-1' 'open'", "kind": "command", "mode": "execute",
  "sensors": {"ai01": 7.5}, "skip_waits": true, "timeout_ms": 15000 }
```
- `kind`: `command` (jedna linia OQL) | `script` (pełny dokument OQL) | `ping`
- `mode`: `execute` | `dry-run` | `validate`
- Odpowiedź: `{ "ok": bool, "result": {...}, "error": str|null, "node_id": str }`
- `503` gdy transport `off`. Timeout → `ok=false` z `error` (nigdy nie rzuca wyjątku).

### `POST /api/v1/oql/manage`
Verb zarządzający/diagnostyczny (patrz §5).
```json
{ "verb": "usb-list", "args": {}, "timeout_ms": 15000 }
```

### `WS /ws/oql`
Kanał dwukierunkowy: klient wysyła `{"oql": "...", "kind": "...", "mode": "..."}`, dostaje
wynik + strumień zdarzeń `{"event": ...}` z agenta.

---

## 5. Verby `manage` (pełna lista)

Wykonywane **na agencie** (realny sprzęt), reużywają handlerów `oqlos.api.hardware`.

### Diagnostyka / status (read-only)
| Verb | Args | Zwraca |
|------|------|--------|
| `health` | — | status pluginów, `mode` |
| `identify` | `{scan: auto\|always\|never}` | platforma, adaptery, porty |
| `diagnose` | — | health + odczyt ai01–ai03 |
| `diagnosis` | `{scan}` | plan diagnozy per-urządzenie |
| `stack-snapshot` | — | health + porty + plan wizard |
| `waveshare-diagnose` | — | skan macierzy Modbus |
| `temperature` | — | temperatura CPU |
| `rtc-status` | — | status RTC |
| `modbus-adc-raw` | — | surowe rejestry ADC |
| `artificial-lung-status` | — | status płuca |

### Diagnostyka RPi3 / USB
| Verb | Args | Zwraca |
|------|------|--------|
| `usb-list` | — | lista urządzeń USB (vid:pid, producent, `port_path`, `tty`, `serial_by_id`) |
| `pi-diagnostics` | — | model, CPU temp, throttled, napięcie, pamięć, uptime, porty, i2c, liczba USB |
| `usb-reset` | `{vendor_id, product_id?, dev_node?}` | reset/re-enumeracja sterownika (wymaga root/udev) |

### Sterowanie / akcje (działają na realnym sprzęcie)
| Verb | Args |
|------|------|
| `valve` | `{valve_id, value}` |
| `pump` | `{power_pct}` |
| `sensor` | `{sensor_id}` |
| `lung` | `{steps, speed, cycles, pause}` |
| `lung-stop` / `lung-disable` | — |
| `rtc-command` / `artificial-lung-command` | `{payload}` |
| `diagnostic-command` | `{peripheral_id, command, args}` — generyczny most do `plugins/{id}/execute` (ścieżka CQRS) |

### Wizard Modbus
`wizard-plan` (—), `wizard-probe` (`{serial_port, baudrates, parities, device_ids, module_role}`),
`wizard-program` (`{serial_port, current_device_id, new_device_id, new_baudrate, new_parity, confirm_isolated}`).

Implementacja: `oqlos/hardware/transport/manage_ops.py`, `oqlos/hardware/usb_diagnostics.py`.

---

## 6. Diagnostyka i sterowanie USB — co możliwe, co nie

- **Lista USB** (`usb-list`): pełna, z sysfs, bez roota. Pola `port_path` (ścieżka fizyczna,
  np. `1-1.5`), `tty` (`/dev/ttyUSB*`), `serial_by_id`.
- **Diagnostyka Pi** (`pi-diagnostics`): model, temperatura, throttling (`get_throttled`), pamięć.
- **Zmiana fizycznego portu USB**: **niemożliwa** programowo — to sprzęt.
- **Reset/re-enumeracja** (`usb-reset`): możliwa (ioctl `USBDEVFS_RESET`), ale wymaga roota
  lub reguły udev (`MODE 0666`) dla urządzenia — verb zwraca czytelny błąd uprawnień.
- **Stabilne nazewnictwo** niezależne od portu: reguły **udev** (`/dev/serial/by-id/...`,
  symlinki typu `/dev/maskservice-tic249`) — konfigurowane w `redeploy/122` (kroki udev).

---

## 7. Wdrożenie

- Węzeł sprzętowy (boardnet): `oqlos/redeploy/122/` — `migration.md` (markpact: mosquitto,
  agent, sidecary, autodetekcja Modbus), `oqlos-hw.yaml`, `.env.hw`, `mosquitto.conf`, `RUNBOOK.md`.
  Wymaga `sudo` na Pi (apt mosquitto, udev, systemd linger).
- Węzeł aplikacyjny (pi109): `c2004/redeploy/pi109/migration.md` — flaga
  `PI109_HARDWARE_REMOTE=1` (domyślnie 0 = stary tryb) odcina lokalny sprzęt, uruchamia
  controller, kieruje backend na broker boardnet.
- Reverse-proxy: `c2004/connect-scenario/nginx.conf.template` — `location /oql-panel`,
  `/api/v1/oql/`, `/ws/oql` → `${OQLOS_CONTROLLER_URL}`.
- **Zależności na Pi**: `oqlos.hardware.client` jest częścią OqlOS; węzeł sprzętowy nie
  wymaga już pakietu `hardware_client` z c2004. Zewnętrzny pozostaje tylko sterownik
  Modbus (`pimodbus`), gdy używany jest bezpośredni dostęp do Waveshare/RTU.

---

## 8. Rozwiązywanie problemów

| Objaw | Przyczyna / rozwiązanie |
|-------|--------------------------|
| `/api/v1/oql/*` zwraca **503** | instancja nie jest w roli `controller` — ustaw `OQLOS_OQL_TRANSPORT_ROLE=controller` |
| **timeout** wszystkich żądań (też ping) | broker padł lub agent nie zasubskrybował — restart **kolejno** broker → agent → controller |
| **ping OK, ale verby timeout** | błąd/zawieszenie w handlerze verba na Pi (nie transport) — sprawdź log agenta |
| panel pusty pod LAN-IP | controller na `127.0.0.1` — uruchom z `--host 0.0.0.0` |
| `usb-reset` → permission denied | brak roota/udev — to oczekiwane bez `sudo` |
| amqtt niestabilny po restartach | `amqtt` to broker dev bez sudo; produkcyjnie użyj **mosquitto** (`redeploy/122`) |

> Uwaga historyczna: `usb-list`/`pi-diagnostics` potrafiły timeout-ować, gdy `_find_tty`
> używał rekurencyjnego globa `**` po sysfs (cykle symlinków → zawieszenie na Pi). Naprawione
> globami bez rekurencji (`oqlos/hardware/usb_diagnostics.py`).
