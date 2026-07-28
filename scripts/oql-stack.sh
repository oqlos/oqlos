#!/usr/bin/env bash
# Zarządza stosem OQL-over-MQTT (tryb dev, bez sudo):
#   broker (amqtt) + agent (oqlos real) na Pi sprzętowym  +  controller (oqlos) lokalnie.
# Po starcie panel jest pod  http://<ten-host>:$CTRL_PORT/panel
#
# Użycie:  scripts/oql-stack.sh {up|down|status|panel}
#
# Konfiguracja przez env (domyślne dla węzła boardnet):
PI=${OQL_PI:-pi@boardnet.local}                         # ssh do Pi sprzętowego
NODE=${OQL_NODE:-boardnet}                               # node_id
PREFIX=${OQL_PREFIX:-oqlos/c2004}                        # prefiks tematów MQTT
BROKER_LAN=${OQL_BROKER_LAN:-192.168.188.122}            # IP brokera widziane przez controller
SERIAL=${OQL_SERIAL:-/dev/ttyUSB0}                       # port Modbus IO na Pi
CTRL_HOST=${OQL_CTRL_HOST:-0.0.0.0}                      # bind controllera (0.0.0.0 = dostęp z LAN)
CTRL_PORT=${OQL_CTRL_PORT:-8210}
OQLOS_DIR=${OQLOS_DIR:-$(cd "$(dirname "$0")/.." && pwd)}
VENV=${OQL_VENV:-$OQLOS_DIR/.venv}
RLOG='~/maskservice/logs'

set -uo pipefail
remote(){ ssh -o ConnectTimeout=10 "$PI" "$@"; }
say(){ printf '\033[36m▸ %s\033[0m\n' "$*"; }
ok(){  printf '\033[32m✓ %s\033[0m\n' "$*"; }
err(){ printf '\033[31m✗ %s\033[0m\n' "$*" >&2; }

wait_tcp(){ # host port tries
  local h=$1 p=$2 n=${3:-20} i
  for ((i=0;i<n;i++)); do (exec 3<>/dev/tcp/$h/$p) 2>/dev/null && { exec 3>&-; return 0; }; sleep 1; done
  return 1
}

up_broker(){
  say "broker amqtt na $PI:1883"
  remote "mkdir -p $RLOG; pgrep -f '[a]mqtt -c' >/dev/null 2>&1 && exit 0; \
          nohup ~/oqlos/venv/bin/amqtt -c ~/maskservice/config/amqtt.yaml >$RLOG/amqtt.log 2>&1 </dev/null & disown; sleep 1"
  wait_tcp "${PI#*@}" 1883 15 && ok "broker :1883" || { err "broker nie wstał"; return 1; }
}

up_agent(){
  say "agent oqlos (real) na $PI:8202"
  remote "mkdir -p $RLOG; ss -ltn 'sport = :8202' 2>/dev/null | grep -q ':8202' && exit 0; \
          cd ~/oqlos/oqlos && OQLOS_HARDWARE_MODE=real OQLOS_MODBUS_SERIAL_PORT=$SERIAL OQLOS_MODBUS_BAUD=4800 \
          OQLOS_OQL_TRANSPORT_ROLE=agent OQLOS_OQL_NODE_ID=$NODE OQLOS_OQL_TOPIC_PREFIX=$PREFIX \
          OQLOS_OQL_MQTT_HOST=127.0.0.1 OQLOS_OQL_MQTT_PORT=1883 \
          nohup ~/oqlos/venv/bin/oqlos-server --host 0.0.0.0 --port 8202 >$RLOG/oqlos-agent.log 2>&1 </dev/null & disown; sleep 1"
  wait_tcp "${PI#*@}" 8202 30 || { err "agent nie wstał"; return 1; }
  # czekaj aż agent MQTT się połączy
  for i in {1..15}; do remote "grep -q 'OqlMqttAgent connected' $RLOG/oqlos-agent.log 2>/dev/null" && { ok "agent :8202 + MQTT connected"; return 0; }; sleep 1; done
  ok "agent :8202 (MQTT connect — sprawdź log)"
}

up_sidecar(){ # opcjonalny sidecar Tic T249 (jeśli wdrożony)
  remote "[ -x ~/maskservice/rpi-motor-tic249/.venv/bin/python ]" || return 0
  say "sidecar Tic T249 na $PI:8205 (opcjonalny)"
  remote "ss -ltn 'sport = :8205' 2>/dev/null | grep -q ':8205' && exit 0; \
          cd ~/maskservice/rpi-motor-tic249 && FLASK_HOST=0.0.0.0 FLASK_PORT=8205 USB_PRODUCT_ID=0x00c9 \
          PATH=~/maskservice/rpi-motor-tic249/.venv/bin:\$PATH \
          nohup ~/maskservice/rpi-motor-tic249/.venv/bin/python web_panel.py >$RLOG/hw-tic249.log 2>&1 </dev/null & disown; sleep 1"
  wait_tcp "${PI#*@}" 8205 10 && ok "sidecar :8205 (wymaga reguły udev dla 1ffb by sięgnąć Tica)" || true
}

up_controller(){
  say "controller oqlos lokalnie :$CTRL_PORT (most HTTP→MQTT do $BROKER_LAN)"
  if (exec 3<>/dev/tcp/127.0.0.1/$CTRL_PORT) 2>/dev/null; then exec 3>&-; ok "controller już działa"; return 0; fi
  mkdir -p /tmp/oql-stack
  ( cd "$OQLOS_DIR" && OQLOS_OQL_TRANSPORT_ROLE=controller OQLOS_OQL_NODE_ID=$NODE OQLOS_OQL_TOPIC_PREFIX=$PREFIX \
    OQLOS_OQL_MQTT_HOST=$BROKER_LAN OQLOS_OQL_MQTT_PORT=1883 OQLOS_HARDWARE_MODE=mock \
    nohup "$VENV/bin/oqlos-server" --host "$CTRL_HOST" --port "$CTRL_PORT" >/tmp/oql-stack/controller.log 2>&1 </dev/null & echo $! >/tmp/oql-stack/controller.pid )
  wait_tcp 127.0.0.1 "$CTRL_PORT" 25 && ok "controller :$CTRL_PORT" || { err "controller nie wstał (log: /tmp/oql-stack/controller.log)"; return 1; }
}

cmd_up(){ up_broker && up_agent && up_sidecar && up_controller && { echo; ok "Stos gotowy. Panel: $(panel_url)"; }; }

cmd_down(){
  say "zatrzymywanie controllera (lokalnie)"
  [ -f /tmp/oql-stack/controller.pid ] && kill "$(cat /tmp/oql-stack/controller.pid)" 2>/dev/null && rm -f /tmp/oql-stack/controller.pid
  say "zatrzymywanie agenta/brokera/sidecara na $PI"
  remote "for P in 8202 8205 1883; do \
            PID=\$(ss -Hltnp \"sport = :\$P\" 2>/dev/null | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2); \
            [ -n \"\$PID\" ] && kill \"\$PID\" 2>/dev/null; done; sleep 1; echo stopped"
  ok "zatrzymano"
}

cmd_status(){
  printf '  %-26s' "broker  $PI:1883"; wait_tcp "${PI#*@}" 1883 1 && ok up || err down
  printf '  %-26s' "agent   $PI:8202"; wait_tcp "${PI#*@}" 8202 1 && ok up || err down
  printf '  %-26s' "sidecar $PI:8205"; wait_tcp "${PI#*@}" 8205 1 && ok up || echo "—"
  printf '  %-26s' "controller :$CTRL_PORT"; wait_tcp 127.0.0.1 "$CTRL_PORT" 1 && ok up || err down
  if wait_tcp 127.0.0.1 "$CTRL_PORT" 1; then
    printf '  węzeł: '
    curl -s --max-time 8 -X POST http://127.0.0.1:$CTRL_PORT/api/v1/oql/manage -H 'Content-Type: application/json' -d '{"verb":"health"}' \
      | python3 -c "import sys,json;d=json.load(sys.stdin);print('node=%s mode=%s ok=%s'%(d.get('node_id'),(d.get('result') or {}).get('mode'),d.get('ok')))" 2>/dev/null || echo "(brak odpowiedzi MQTT)"
  fi
}

panel_url(){ local ip; ip=$(hostname -I 2>/dev/null | awk '{print $1}'); echo "http://${ip:-127.0.0.1}:$CTRL_PORT/panel"; }

case "${1:-}" in
  up)     cmd_up ;;
  down)   cmd_down ;;
  status) cmd_status ;;
  panel)  panel_url ;;
  *) echo "Użycie: $0 {up|down|status|panel}"; exit 2 ;;
esac
