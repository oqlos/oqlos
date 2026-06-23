# boardnet (122) provisioning runbook (192.168.188.122)

One-time bare-metal setup for the dedicated OqlOS hardware Raspberry Pi 3. Run these
**before** the first `redeploy run redeploy/122/migration.md`. After provisioning, all
software bring-up is handled by `migration.md` (the `markpact:ref` scripts are also
runnable standalone over ssh if you prefer manual control).

## 1. Operating system
- Flash **Raspberry Pi OS Lite (64-bit)** to the SD card.
- Hostname `boardnet`; user `pi`.
- Wired **ethernet** (Modbus-over-network latency: avoid Wi-Fi).
- Reserve **192.168.188.122** for the Pi's MAC in the router DHCP table (static lease).

## 2. SSH access
```bash
ssh-copy-id pi@boardnet.local          # from the laptop/pi109 that runs redeploy
ssh pi@boardnet.local true             # verify key-only login works
```

## 3. Base packages
```bash
ssh pi@boardnet.local 'sudo apt-get update && \
  sudo apt-get install -y python3-venv python3-pip mosquitto mosquitto-clients'
```
If the RTC HAT is fitted, enable I2C:
```bash
ssh pi@boardnet.local 'sudo raspi-config nonint do_i2c 0'
```

## 4. systemd --user + device groups
```bash
ssh pi@boardnet.local 'sudo loginctl enable-linger pi && \
  sudo usermod -aG dialout,plugdev,i2c,gpio pi'
```
(The `enable-linger-groups` deploy step repeats this idempotently.)

## 5. MQTT broker secret
The broker requires auth (`allow_anonymous false`). Choose a token and set it on the Pi
**before** deploying — `install-mosquitto` reads it to create `mosquitto.passwd`:
```bash
ssh pi@boardnet.local 'mkdir -p ~/maskservice/config && \
  printf "OQLOS_OQL_MQTT_PASSWORD=%s\n" "<your-token>" >> ~/maskservice/config/oql-mqtt.env'
```
Use the **same token** on pi109 (see `redeploy/pi109/migration.md` → `point_oqlos_at_remote`).

## 6. Plug in the hardware
USB hub on boardnet with: Pololu Tic T249 (`1ffb:00c9`), Waveshare Modbus IO 8CH (`1a86`),
Modbus ADC adapter, and the RTC WatchDog HAT on the GPIO header (if used). These devices
move **off pi109** onto this Pi.

## 7. Deploy
```bash
# From the oqlos repo on the laptop/pi109:
redeploy run redeploy/122/migration.md
# Bench mode (devices not all present yet):
PIHW_ALLOW_MISSING_HARDWARE=1 redeploy run redeploy/122/migration.md
```

## 8. Verify
```bash
ssh pi@boardnet.local 'systemctl --user is-active mosquitto oqlos-hardware-api hw-tic249 dri0050-motor-api pirtc-api'
ssh pi@boardnet.local 'mosquitto_sub -u oqlos -P "<token>" -t "\$SYS/broker/uptime" -C 1'
# From pi109, confirm the OQL agent answers a ping over MQTT (assert-hw-node-healthy does this).
```

## 9. Point pi109 at this node
Provision/verify here first, then on pi109 run:
```bash
PI109_HARDWARE_REMOTE=1 redeploy run redeploy/pi109/migration.md
```
That guards out pi109's local hardware steps and repoints its backend/OQL controller at
`192.168.188.122` (`OQLOS_API_URL` + `OQLOS_OQL_MQTT_HOST`). See the **Hardware Separation**
section of `redeploy/pi109/migration.md`.

## Ports on boardnet
| Service | Port | Exposure |
|---|---|---|
| mosquitto (MQTT broker) | 1883 | LAN (pi109 connects here) |
| oqlos-hardware-api (HTTP/agent) | 8202 | **loopback only** |
| hw-tic249 | 8205 | loopback only |
| dri0050-motor-api | 8203 | loopback only |
| pirtc-api | 8125 | loopback only |

## Rollback to single-Pi
If boardnet is unavailable, redeploy pi109 **without** the flag
(`PI109_HARDWARE_REMOTE=0`, the default) and move the USB devices/HAT back to pi109. pi109's
original hardware steps run unchanged.
