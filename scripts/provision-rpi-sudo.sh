#!/usr/bin/env bash
#
# OqlOS — RPi hardware-node sudo provisioning.
# Uruchom LOKALNIE na Raspberry Pi z sudo. Idempotentny.
#
# Odblokowuje to, czego nie da się zrobić bez roota:
#   1. dostęp do USB bez roota (Pololu Tic T249 + CH340/DRI0050/Modbus) — reguły udev MODE 0666
#   2. trwałe usługi systemd --user (linger) — przetrwają wylogowanie i reboot
#   3. grupy urządzeń (dialout, plugdev, i2c, gpio)
#   4. (opcjonalnie) broker mosquitto dla ścieżki OQL-over-MQTT
#
# Użycie (na Pi):
#   sudo bash provision-rpi-sudo.sh                      # USB udev + linger + grupy
#   WITH_MOSQUITTO=1 sudo bash provision-rpi-sudo.sh     # dodatkowo instaluje mosquitto
#
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "FAIL: uruchom z sudo —  sudo bash $0" >&2
  exit 1
fi

TARGET_USER="${SUDO_USER:-pi}"
echo "== OqlOS RPi provisioning (user=$TARGET_USER) =="

# 1) Grupy urządzeń (idempotentne)
usermod -aG dialout,plugdev,i2c,gpio "$TARGET_USER" 2>/dev/null || true
echo "PASS: grupy dialout,plugdev,i2c,gpio dla $TARGET_USER (zadziałają po ponownym logowaniu)"

# 2) Linger — usługi systemd --user przeżywają wylogowanie / reboot
loginctl enable-linger "$TARGET_USER"
echo "PASS: linger włączony dla $TARGET_USER"

# 3) Reguły udev — dostęp do USB bez roota (MODE 0666)
cat > /etc/udev/rules.d/99-oqlos-hw.rules <<'RULES'
# Pololu Tic T249 — stepper "sztucznego płuca"
SUBSYSTEM=="usb", ATTR{idVendor}=="1ffb", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1ffb", ATTRS{idProduct}=="00c9", SYMLINK+="oqlos-tic249", MODE="0666", GROUP="plugdev"
# CH340 / DFRobot DRI0050 + Modbus USB-serial
SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", MODE="0666", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", MODE="0666", GROUP="dialout"
RULES
udevadm control --reload-rules
udevadm trigger -s usb  2>/dev/null || true
udevadm trigger -s tty  2>/dev/null || true
# Zastosuj od razu do już podłączonych węzłów (bez przepinania kabla)
find /dev/bus/usb -type c -exec chmod a+rw {} + 2>/dev/null || true
echo "PASS: udev /etc/udev/rules.d/99-oqlos-hw.rules + bieżące węzły USB a+rw"

# 4) Opcjonalnie: broker mosquitto (sam broker uruchamia redeploy jako systemd --user)
if [ "${WITH_MOSQUITTO:-0}" = "1" ]; then
  if ! command -v mosquitto >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y mosquitto mosquitto-clients
  fi
  # Wyłącz systemowy broker — OqlOS uruchamia go rootless przez systemd --user.
  systemctl disable --now mosquitto 2>/dev/null || true
  echo "PASS: mosquitto zainstalowany (broker odpala redeploy jako systemd --user na :1883)"
else
  echo "SKIP: mosquitto (ustaw WITH_MOSQUITTO=1 aby zainstalować)"
fi

echo
echo "== DONE =="
echo "Weryfikacja USB:  ls -l /dev/oqlos-tic249  /dev/bus/usb/*/*"
echo "Następnie (bez sudo) można uruchomić real-hardware oqlos-server,"
echo "albo pełne wdrożenie:  redeploy run redeploy/122/migration.md"
