# OqlOS BoardNet — aktualny stan

Ostatnio sprawdzono: 2026-06-30 13:58 Europe/Warsaw.

## Rola

- **BoardNet / RPi3**: `pi@192.168.188.122`
  - Hostname systemowy: `boardnet.local`.
  - Właściciel produkcyjnego OqlOS firmware i bezpośrednio podłączonego hardware.
  - OqlOS API/UI: `:8202`; DRI0050: `:8203`; Tic249: `:8205`; piRTC: `:8125`.
- **DisplayNet / RPi5**: `pi@192.168.188.109`
  - Hostname systemowy: `displaynet`.
  - Właściciel GUI/kiosku/orchestracji c2004.
  - Do BoardNet idzie przez `OQLOS_API_URL=http://192.168.188.122:8202`.

## Ścieżka sterowania

```text
Browser/HUI on DisplayNet :8100
  -> /api/v3/hardware/* on c2004/connect-scenario backend
  -> OQLOS_API_URL=http://192.168.188.122:8202
  -> OqlOS on BoardNet
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
curl -s http://192.168.188.122:8205/api/status
curl -s http://192.168.188.122:8203/health
```

## Zdrowe elementy

- `oqlos-hardware-api.service`, `hw-tic249.service`,
  `dri0050-motor-api.service`, `mosquitto.service` i `pirtc-api.service` są
  aktywne.
- Po reboot BoardNet `.122` wszystkie powyższe usługi wróciły jako `active`,
  a `systemctl --user --failed` był pusty.
- USB widoczne na BoardNet:
  - Pololu Tic T249: `1ffb:00c9`
  - CH340 USB Single Serial: `/dev/ttyACM0`
  - CH340 USB2.0-Serial: `/dev/ttyUSB0`
- Tic249 raportuje `connected=true`, `energized=false`.
- DRI0050 raportuje zdrowy stan na `:8203`.
- Modbus-IO raportuje `status=connected`, `compatible=true`.
- OqlOS działa w `mode=real`, `overall_ok=true`, `degraded=false`.
- `modbus-adc` jest świadomie wyłączony (`enabled=false`, `status=disabled`),
  ponieważ adapter ADC nie jest obecny.

## Ostatnia naprawa

- Read-only `pimodbus.provision_cli diagnose` znalazł Waveshare Modbus-IO na:
  `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5958006895-if00`,
  `9600/N`, slave ID `2`.
- Nie programowano modułu i nie wykonywano `repair --yes`.
- Poprawiono konfigurację runtime na `modbus-io.device_id=2` oraz
  `OQLOS_MODBUS_DEVICE_ID=2`.
- `redeploy/122/migration.md` wykrywa teraz slave ID dla `modbus-io`, więc
  ponowny deploy nie powinien cofnąć ustawienia do ID `1`.

## Wykonana diagnostyka read-only

- Zatrzymano tylko `oqlos-hardware-api.service`, sidecary zostawiono aktywne,
  potem firmware został ponownie uruchomiony.
- Krótki skan targetowany (`9600`, parity `N`, IDs `1,2`) wykrył odpowiedź
  `read_coils` dla ID `2`.
- Po restarcie OqlOS: `modbus-io` jest healthy, Tic249 nadal
  `energized=false`.
- Po reboot BoardNet: Tic249 nadal `energized=false`.

Powiązany snapshot po stronie c2004:
`/home/tom/github/maskservice/c2004/redeploy/pi109/CURRENT_STATE.md`.
