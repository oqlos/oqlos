# Systemd service control + startup diagnostics (hardware node)

New OqlOS hardware-node capabilities surfaced to the C2004 UI
(`connect-test → System — procesy`). All routes are under
`/api/v3/hardware` and reachable from pi109/desktop via the existing proxy.

## Routes

| Method | Route | Purpose |
|---|---|---|
| GET  | `/api/v3/hardware/systemd/services` | Status of every whitelisted unit |
| POST | `/api/v3/hardware/systemd/services/{unit}/{action}` | `start`/`stop`/`restart`/`status` (whitelist-guarded) |
| GET  | `/api/v3/hardware/systemd/services/{unit}/logs?lines=N` | Recent journal lines |
| GET  | `/api/v3/hardware/startup-diagnostics` | Cached boot diagnosis + auto-repair result |

Non-whitelisted units return **403**. Unknown actions return **400**.

## Whitelist

Default (the BoardNet `--user` units, see `redeploy/122/migration.md`):

```
oqlos-hardware-api.service  hw-tic249.service  dri0050-motor-api.service
pirtc-api.service           mosquitto.service
```

Override with `OQLOS_SYSTEMD_WHITELIST` (comma-separated). Bare names get a
`.service` suffix automatically.

## Scope: `--user` (default) vs `system`

On pi-hw these services are **`systemctl --user`** units owned by `pi`
(`~/.config/systemd/user/`, linger enabled). The OqlOS process is that same
user, so it controls them with **no sudo**:

```
systemctl --user restart oqlos-hardware-api.service   # what the API runs
```

Set `OQLOS_SYSTEMD_SCOPE=system` only if the whitelisted units are *system*
units. Then control uses `sudo -n systemctl …` and needs passwordless sudo:

```
# /etc/sudoers.d/oqlos-systemd   (visudo -f)  — ONLY for OQLOS_SYSTEMD_SCOPE=system
pi ALL=(root) NOPASSWD: /usr/bin/systemctl start   oqlos-hardware-api.service, \
                        /usr/bin/systemctl stop    oqlos-hardware-api.service, \
                        /usr/bin/systemctl restart oqlos-hardware-api.service, \
                        /usr/bin/systemctl start   hw-tic249.service, \
                        /usr/bin/systemctl stop    hw-tic249.service, \
                        /usr/bin/systemctl restart hw-tic249.service, \
                        /usr/bin/systemctl start   dri0050-motor-api.service, \
                        /usr/bin/systemctl stop    dri0050-motor-api.service, \
                        /usr/bin/systemctl restart dri0050-motor-api.service, \
                        /usr/bin/systemctl start   pirtc-api.service, \
                        /usr/bin/systemctl stop    pirtc-api.service, \
                        /usr/bin/systemctl restart pirtc-api.service, \
                        /usr/bin/systemctl start   mosquitto.service, \
                        /usr/bin/systemctl stop    mosquitto.service, \
                        /usr/bin/systemctl restart mosquitto.service
```

The default `--user` scope needs **no sudoers change**. (`/host/reboot` still
needs its own `NOPASSWD: /usr/bin/systemctl reboot`, unchanged.)

## Startup diagnostics + auto-repair

Runs in the app lifespan after plugin init (`startup_diagnostics.py`). If the
diagnosis is degraded it attempts `execute_safe_recover`; the result is cached
and served at `/api/v3/hardware/startup-diagnostics`. Never blocks boot.

| Env | Default | Effect |
|---|---|---|
| `OQLOS_STARTUP_DIAGNOSTICS` | `1` | run diagnosis at startup |
| `OQLOS_STARTUP_AUTO_REPAIR` | `1` | attempt safe repair when degraded |

## Deploy

```bash
# fast, code-only (editable install → rsync + restart):
redeploy/pi-hw/push-hw-node-code.sh

# or full provisioning from c2004:
scripts/redeploy/deploy-fleet.sh --only 122
```
