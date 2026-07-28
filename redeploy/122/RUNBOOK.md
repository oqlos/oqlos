# BoardNet provisioning runbook

One-time bare-metal setup for the dedicated OqlOS hardware Raspberry Pi 3. Run these
**before** the first real c2004 `deploy-fleet.sh --only 122` run. After
provisioning, all software bring-up is handled by the canonical migration.

Aktualny stan BoardNet/DisplayNet i ostatniej diagnostyki hardware:
`redeploy/122/CURRENT_STATE.md`.

## 1. Operating system
- Flash **Raspberry Pi OS Lite (64-bit)** to the SD card.
- Hostname `boardnet`; user `pi`.
- Wired **ethernet** (Modbus-over-network latency: avoid Wi-Fi).
- Reserve the `BOARDNET_IP` configured in c2004
  `env.d/21-boardnet-redeploy.env` for the Pi's MAC in the router DHCP table.

Load that profile once in the shell used for the commands below:

```bash
cd /home/tom/github/maskservice/c2004
cp -n env.d/21-boardnet-redeploy.env.example env.d/21-boardnet-redeploy.env
chmod 600 env.d/21-boardnet-redeploy.env
set -a; . env.d/21-boardnet-redeploy.env; set +a
BOARDNET_HOST="${BOARDNET_SSH_USER}@${BOARDNET_IP}"
BOARDNET_SSH=(ssh -p "$BOARDNET_SSH_PORT" -i "$BOARDNET_SSH_KEY")
```

## 2. SSH access
```bash
ssh-copy-id -p "$BOARDNET_SSH_PORT" -i "${BOARDNET_SSH_KEY}.pub" "$BOARDNET_HOST"
"${BOARDNET_SSH[@]}" "$BOARDNET_HOST" true
```

## 3. Base packages
```bash
"${BOARDNET_SSH[@]}" "$BOARDNET_HOST" 'sudo apt-get update && \
  sudo apt-get install -y python3-venv python3-pip mosquitto mosquitto-clients i2c-tools'
```
If the RTC HAT is fitted, enable I2C. The migration repeats this idempotently,
but a reboot may be required after the first enable:
```bash
"${BOARDNET_SSH[@]}" "$BOARDNET_HOST" 'sudo raspi-config nonint do_i2c 0'
```

## 4. systemd --user + device groups
```bash
"${BOARDNET_SSH[@]}" "$BOARDNET_HOST" "sudo loginctl enable-linger '$BOARDNET_SSH_USER' && \
  sudo usermod -aG dialout,plugdev,i2c,gpio '$BOARDNET_SSH_USER'"
```
(The `enable-linger-groups` deploy step repeats this idempotently.)

## 5. MQTT broker secret
The broker requires auth (`allow_anonymous false`). Choose a token and set it on the Pi
**before** deploying — `install-mosquitto` reads it to create `mosquitto.passwd`:
```bash
"${BOARDNET_SSH[@]}" "$BOARDNET_HOST" 'mkdir -p ~/maskservice/config && \
  printf "OQLOS_OQL_MQTT_PASSWORD=%s\n" "<your-token>" >> ~/maskservice/config/oql-mqtt.env'
```
Use the **same token** on pi109 (see `redeploy/pi109/migration.md` → `point_oqlos_at_remote`).

## 6. Plug in the hardware
USB hub on boardnet with: Pololu Tic T249 (`1ffb:00c9`), Waveshare Modbus IO 8CH (`1a86`),
Modbus ADC adapter, and the RTC WatchDog HAT on the GPIO header (if used). These devices
move **off pi109** onto this Pi.

## 7. Deploy
```bash
# From the c2004 repository:
scripts/redeploy/deploy-fleet.sh --only 122
# Bench mode (devices not all present yet):
PIHW_ALLOW_MISSING_HARDWARE=1 scripts/redeploy/deploy-fleet.sh --only 122
```

## 8. Verify
```bash
"${BOARDNET_SSH[@]}" "$BOARDNET_HOST" 'systemctl --user is-active mosquitto oqlos-hardware-api hw-tic249 dri0050-motor-api pirtc-api'
"${BOARDNET_SSH[@]}" "$BOARDNET_HOST" 'mosquitto_sub -u oqlos -P "<token>" -t "\$SYS/broker/uptime" -C 1'
# From pi109, confirm the OQL agent answers a ping over MQTT (assert-hw-node-healthy does this).
```

## 9. Point DisplayNet/pi109 at this node
Provision/verify here first, then deploy c2004 DisplayNet/pi109 with the current
split configuration:
```bash
scripts/redeploy/deploy-pi109.sh
```
That stops/skips DisplayNet local hardware services and points c2004 backend/proxy
at `OQLOS_API_URL=http://${BOARDNET_IP}:${BOARDNET_OQLOS_PORT}`. See the **Hardware Separation**
section of `/home/tom/github/maskservice/c2004/redeploy/pi109/migration.md`.

## Ports on boardnet
| Service | Port | Exposure |
|---|---|---|
| mosquitto (MQTT broker) | 1883 | LAN (pi109 connects here) |
| oqlos-hardware-api (HTTP/UI/agent) | 8202 | LAN (c2004 DisplayNet connects here) |
| hw-tic249 | 8205 | LAN/local lab only |
| dri0050-motor-api | 8203 | LAN/local lab only |
| pirtc-api | 8125 | LAN/local lab only |

Do not expose these ports outside the trusted lab LAN.

## Current hardware note

As of 2026-07-27 14:37 CEST, BoardNet is up in `mode=real` with
`overall_ok=true`. Tic249 and DRI0050 are healthy, Tic249 is de-energized when
idle, Modbus-IO is configured for `4800/N/8/1`, slave ID `1`, and piRTC reports
`rtc.available=true`, `watchdog.available=true`, `mock=false` on `:8125`.
`modbus-adc` is disabled because the ADC adapter is not present.

## Rollback to single-Pi
If boardnet is unavailable, set `PI109_HARDWARE_LOCAL=1` in the c2004 deployment
and move the USB devices/HAT back to DisplayNet/pi109. That is legacy/rollback
mode, not the current production split.
