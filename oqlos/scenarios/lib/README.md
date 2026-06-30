# `lib/` — biblioteki makr OQL v3

Makra (`MACRO name:`) pozwalają enkapsulować powtarzające się fragmenty
scenariuszy bez rozdymania zestawu komend bazowych (12 komend, patrz
`docs/oql-spec.md`).

## Jak używać

```oql
INCLUDE "lib/hardware.oql"
INCLUDE "lib/peripherals.oql"

CONFIG reset:
  CALL init-all

GOAL smoke:
  CALL hw-pump-smoke
  CALL hw-valves-smoke
  CALL hw-sensors-baseline
```

`INCLUDE` jest rozwiązywany względem:

1. ścieżki absolutnej (jeśli podana),
2. katalogu pliku wywołującego,
3. `oqlos/scenarios/` (korzeń scenariuszy).

## Argumenty pozycjonalne

```oql
MACRO set-pump-lpm:
  SET pump-main $1 l/min
  WAIT $2

GOAL ramp:
  CALL set-pump-lpm 3 500ms
  CALL set-pump-lpm 5 500ms
  CALL set-pump-lpm 0 200ms
```

Podstawienie `$1`, `$2`, ... jest wykonywane na tekście linii przed
tokenizacją — dzięki czemu argumenty mogą zawierać liczbę, identyfikator
lub całą jednostkę.

## Pliki

| Plik | Makra |
|---|---|
| `hardware.oql` | `hw-pump-smoke`, `hw-pump-off`, `hw-valves-reset`, `hw-valves-smoke`, `hw-lung-smoke`, `hw-sensors-baseline` |
| `peripherals.oql` | `init-pump`, `init-valves-main`, `init-valves-bo`, `init-valves-numbered`, `init-all`, `stop-all` |
