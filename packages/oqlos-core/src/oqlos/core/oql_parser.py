"""
OQL parser (v3 + v4 + v5 compatibility) — flat, quote-free syntax.

Design (see docs/oql-spec.md):
  * 12 base commands:
      SET, GET (alias READ), WAIT, SAVE, CHECK, MIN, MAX,
      SAMPLE, LOG, ERROR, CALL, INCLUDE
  * Block headers: ``GOAL name:``, ``CONFIG name:``, ``MACRO name:``
  * Metadata header lines: ``SCENARIO: ...``, ``DEVICE: ...``, ``DESCRIPTION: ...``
    (uppercase key before colon, free text after).
  * Identifiers are UTF-8 (Polish characters are fine).
  * Identifiers containing whitespace must be written as ``[two words]``.
  * Quoted strings ``"..."`` or ``'...'`` are only used for LOG/ERROR/INCLUDE
    messages; everything else is token-based (no ``=``, no quoting).
  * Units can contain ``/`` and ``%`` (e.g. ``l/min``, ``%RH``, ``°C``, ``m³/h``).

The parser purposely does NOT implement control flow, variables or macro
expansion — it produces a static AST (``OqlDoc``) which the interpreter
(or an adapter) consumes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .oql_versioning import (
    OQL_VERSION_LEGACY,
    OQL_VERSION_V4,
    SUPPORTED_OQL_VERSIONS,
    resolve_oql_version,
)

# ── Regex building blocks ─────────────────────────────────────────

#: Numeric literal (int or float, optional sign).
NUM = r"-?\d+(?:[.,]\d+)?"

#: Duration: number optionally glued to a time unit (``3s``, ``500ms``, ``3000``).
DUR_RE = re.compile(rf"^({NUM})(ms|s|m|h)?$")

#: Header of a block: ``GOAL name:``, ``CONFIG name:``, ``HARDWARE:``, ``EVENT name:``, ``MACRO name:``, ``FUNC name:``.
#: ``TEST:`` is the 2026-07 dialect spelling of a runnable block — parsed as GOAL.
BLOCK_RE = re.compile(r"^(GOAL|TEST|CONFIG|HARDWARE|EVENT|MACRO|FUNC)(?:\s+(.+?))?:\s*$", re.IGNORECASE)

#: Forma zgodności c2004: ``FUNC: nazwa`` (nazwa PO dwukropku, jak we frontendzie
#: ``parseOqlToSteps._startFunc``). Rozpoznawana jako nagłówek bloku FUNC, nie
#: jako metadane. Zawężone do FUNC — ``GOAL: Nazwa`` w dialekcie flat pozostaje
#: błędem (v4+ wymaga nazwy przez ``NAME``).
FUNC_INLINE_NAME_RE = re.compile(r"^FUNC\s*:\s*(.+)$", re.IGNORECASE)

#: Metadata line: ``KEY: value`` (KEY is UPPER_SNAKE).
META_RE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*:\s*(.+)$")

#: Inline access grants are interpreted by the editor/store policy layer.  The
#: execution parser deliberately ignores them, just like comments/metadata, so
#: the same OQL source remains valid in the Python and browser runtimes.
GRANT_RE = re.compile(
    r"^(ALLOW|DENY)\s+(role|persona):[A-Za-z0-9_-]+\s+"
    r"(READ|CREATE|UPDATE|DELETE)\s+(\*|[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+(?:'[^']*'|\"[^\"]*\"|\*))?\s*$",
    re.IGNORECASE,
)

#: ``CHECK`` clause: ``min <= sensor <= max unit``.
CHECK_RE = re.compile(
    rf"^({NUM})\s*<=\s*(\S+)\s*<=\s*({NUM})(?:\s+(\S+))?$"
)

#: ``IF`` range clause: ``sensor min .. max [unit]``.
IF_RE = re.compile(
    rf"^(\S+)\s+({NUM})\s*\.\.\s*({NUM})(?:\s+(\S+))?$"
)

#: ``IF`` comparison clause (legacy quoted style):
#: ``'param' <op> 'value' [OR 'param2' <op2> 'value2'] [ELSE ...]``.
IF_CMP_RE = re.compile(
    r"^'([^']*)'\s*([<>=≤≥!]+)\s*'([^']*)'"
    r"(?:\s+OR\s+'([^']*)'\s*([<>=≤≥!]+)\s*'([^']*)')?"
    r"(?:\s+ELSE\s+(.+))?$",
    re.IGNORECASE,
)

DELTA_RE = re.compile(r"^([+-]?\d+(?:[\.,]\d+)?)(.*)$")

#: Whitelisted metadata keys.  Unknown ``KEY:`` lines at the top level are
#: still captured in :pyattr:`OqlDoc.meta` but emit a warning.
_KNOWN_META_KEYS = {
    "SCENARIO",
    "DEVICE",
    "DEVICE_TYPE",
    "DEVICE_MODEL",
    "MANUFACTURER",
    "CATEGORY",
    "DESCRIPTION",
    "VERSION",
    "AUTHOR",
    "TAGS",
}


# ── AST node types ───────────────────────────────────────────────


@dataclass
class OqlCmd:
    """A single command line inside a block."""

    cmd: str
    args: dict = field(default_factory=dict)
    line: int = 0
    raw: str = ""

    def __repr__(self) -> str:
        rendered = "  ".join(
            f"{k}={v}" for k, v in self.args.items() if v is not None
        )
        return f"{self.cmd:<8} {rendered}"


@dataclass
class OqlBlock:
    """A named block: ``GOAL``, ``CONFIG``, or ``MACRO``.

    MACRO blocks store their body as raw command lines in
    :pyattr:`raw_cmds` because the body may reference ``$1``…``$N``
    placeholders that are only resolvable at expansion time.
    """

    type: str  # GOAL | CONFIG | MACRO
    name: str
    cmds: list[OqlCmd] = field(default_factory=list)
    raw_cmds: list[tuple[int, str]] = field(default_factory=list)
    line: int = 0


@dataclass
class OqlDoc:
    """Parsed OQL document."""

    meta: dict[str, str] = field(default_factory=dict)
    blocks: list[OqlBlock] = field(default_factory=list)
    includes: list[OqlCmd] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    filename: str = ""
    oql_version: int = OQL_VERSION_LEGACY
    declared_version: int | None = None

    # Convenience helpers ---------------------------------------------------

    def goals(self) -> list[OqlBlock]:
        return [b for b in self.blocks if b.type == "GOAL"]

    def configs(self) -> list[OqlBlock]:
        return [b for b in self.blocks if b.type == "CONFIG"]

    def macros(self) -> list[OqlBlock]:
        return [b for b in self.blocks if b.type == "MACRO"]

    def funcs(self) -> list[OqlBlock]:
        return [b for b in self.blocks if b.type == "FUNC"]

    def events(self) -> list[OqlBlock]:
        return [b for b in self.blocks if b.type == "EVENT"]

    def hardware(self) -> list[OqlBlock]:
        return [b for b in self.blocks if b.type == "HARDWARE"]


# ── Conversion helpers ───────────────────────────────────────────


def to_num(raw: str) -> float | int:
    """Convert '6.0' → 6.0, '3' → 3, '-10,5' → -10.5 (accepts comma)."""
    value = float(str(raw).replace(",", "."))
    return int(value) if value == int(value) else value


def _compact_duration(token: str) -> str:
    return re.sub(r"\s+", "", str(token or "").strip())


def parse_duration(token: str) -> tuple[float | int, str]:
    """Parse ``3s``, ``500ms``, ``3000`` (bare number defaults to ``ms``)."""
    compact = _compact_duration(token)
    match = DUR_RE.match(compact)
    if not match:
        raise ValueError(f"Nieprawidłowy czas: {token!r}")
    return to_num(match.group(1)), match.group(2) or "ms"


def duration_to_ms(token: str) -> int:
    """Convert a duration token into integer milliseconds."""
    value, unit = parse_duration(token)
    multiplier = {"ms": 1, "s": 1000, "m": 60_000, "h": 3_600_000}[unit]
    return int(value * multiplier)


# ── Tokenizer ────────────────────────────────────────────────────

_ESCAPE_RE = re.compile(r"\\(.)")


def _unescape(text: str) -> str:
    return _ESCAPE_RE.sub(lambda m: m.group(1), text)


def tokenize(rest: str) -> list[str]:
    """Split a command tail into tokens.

    Understands three token shapes:

    * ``"double quoted"`` and ``'single quoted'`` strings (backslash escapes).
    * ``[bracketed identifier with spaces]``.
    * Bare tokens — any run of non-whitespace characters.
    """

    tokens: list[str] = []
    i = 0
    n = len(rest)
    while i < n:
        ch = rest[i]
        if ch.isspace():
            i += 1
            continue
        if ch in ('"', "'"):
            quote = ch
            j = i + 1
            buf: list[str] = []
            while j < n:
                cur = rest[j]
                if cur == "\\" and j + 1 < n:
                    buf.append(rest[j + 1])
                    j += 2
                    continue
                if cur == quote:
                    break
                buf.append(cur)
                j += 1
            if j >= n:
                raise ValueError(f"Niedomknięty cudzysłów w: {rest!r}")
            tokens.append("".join(buf))
            i = j + 1
            continue
        if ch == "[":
            j = rest.find("]", i + 1)
            if j < 0:
                raise ValueError(f"Niedomknięty nawias [] w: {rest!r}")
            tokens.append(_unescape(rest[i + 1 : j]).strip())
            i = j + 1
            continue
        # bare token — run up to whitespace
        j = i
        while j < n and not rest[j].isspace():
            j += 1
        tokens.append(rest[i:j])
        i = j
    return tokens


# ── Command parsers ──────────────────────────────────────────────


def _require(tokens: list[str], minimum: int, cmd: str, ln: int, shape: str) -> None:
    if len(tokens) < minimum:
        raise ValueError(f"{cmd} wymaga: {shape} (linia {ln})")


def _split_value_unit(tokens: list[str]) -> tuple[float | int, Optional[str]]:
    value = to_num(tokens[0])
    unit = tokens[1] if len(tokens) > 1 else None
    return value, unit


def _split_set_value_unit(tokens: list[str]) -> tuple[float | int | str, Optional[str]]:
    try:
        return _split_value_unit(tokens)
    except ValueError:
        return " ".join(tokens), None


def parse_SET(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 2, "SET", ln, "target value [unit]")
    target = tokens[0]
    if str(target or "").strip().upper() in {"WAIT", "DELAY", "PAUSE", "TIMEOUT"}:
        return parse_WAIT(tokens[1:], ln, raw)
    value, unit = _split_set_value_unit(tokens[1:])
    return OqlCmd("SET", {"target": target, "value": value, "unit": unit}, ln, raw)


def _make_single_field_parser(cmd: str, field: str, required_desc: str):
    """Factory: require one token, return OqlCmd(cmd, {field: tokens[0]})."""
    def parser(tokens: list[str], ln: int, raw: str) -> OqlCmd:
        _require(tokens, 1, cmd, ln, required_desc)
        return OqlCmd(cmd, {field: tokens[0]}, ln, raw)
    return parser


parse_GET = _make_single_field_parser("GET", "sensor", "sensor")


def parse_WAIT(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 1, "WAIT", ln, "duration")
    raw_token = " ".join(str(token) for token in tokens).strip()
    value, unit = parse_duration(raw_token)
    ms = duration_to_ms(raw_token)
    return OqlCmd(
        "WAIT",
        {"ms": ms, "value": value, "unit": unit, "raw": raw_token},
        ln,
        raw,
    )


def parse_IF_DELTA(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 3, "IF_DELTA", ln, "sensor duration signed-threshold")
    sensor = tokens[0]
    duration_token = str(tokens[1]).replace(" ", "")
    try:
        window_ms = duration_to_ms(duration_token)
    except ValueError as exc:
        raise ValueError(f"IF_DELTA: {exc}") from exc

    match = DELTA_RE.match(str(tokens[2]).strip())
    if not match:
        raise ValueError(
            f"IF_DELTA wymaga: signed-threshold jak +0.1l/min lub -0.1l/min (linia {ln})"
        )

    signed_value = to_num(match.group(1))
    threshold = abs(float(signed_value))
    operator = ">" if signed_value > 0 else "<" if signed_value < 0 else "="
    unit = match.group(2).strip() or None
    window_seconds = window_ms / 1000.0
    return OqlCmd(
        "IF_DELTA",
        {
            "sensor": sensor,
            "window_ms": window_ms,
            "window_s": window_seconds,
            "operator": operator,
            "threshold": threshold,
            "unit": unit,
        },
        ln,
        raw,
    )


parse_SAVE = _make_single_field_parser("SAVE", "label", "label")


def parse_CHECK(rest: str, ln: int, raw: str) -> OqlCmd:
    match = CHECK_RE.match(rest.strip())
    if not match:
        raise ValueError(
            f"CHECK wymaga: min <= sensor <= max [unit] (linia {ln})"
        )
    return OqlCmd(
        "CHECK",
        {
            "min": to_num(match.group(1)),
            "sensor": match.group(2),
            "max": to_num(match.group(3)),
            "unit": match.group(4),
        },
        ln,
        raw,
    )


#: Bound token: number with optional unit ('-10 mbar', '0.5 l/min', '999999').
_BOUND_RE = re.compile(rf"^({NUM})\s*(.*)$")


def _parse_bound(token: str) -> tuple[float | int | None, str]:
    """'-10 mbar' → (-10, 'mbar'); non-numeric token → (None, '')."""
    match = _BOUND_RE.match(str(token).strip())
    if not match:
        return None, ""
    return to_num(match.group(1)), match.group(2).strip()


def _parse_if_quoted_range(rest: str, ln: int, raw: str) -> OqlCmd | None:
    """Toleruj legacy zakresy z konwersji CQL/XML:

    ``IF 'param' 'min u' .. 'max u'`` — cytowane granice z jednostką,
    ``IF 'ciśnienie' 'NC' '-10 mbar' .. 'NC' '0 mbar'`` — etykiety scalane
    do nazwy parametru (lewa) / ignorowane (prawa),
    ``IF 'param' '0 .. 1100 N'`` — zakres w jednym cytowanym tokenie,
    ``IF 'timer' 'timeout' .. 999999`` — granica jako nazwa zmiennej
    (rozwiązywana w runtime).
    """
    tokens = tokenize(rest.strip())
    if ".." not in tokens:
        for idx, tok in enumerate(tokens):
            if ".." in tok and tok != "..":
                left_part, _, right_part = tok.partition("..")
                expanded = tokens[:idx]
                if left_part.strip():
                    expanded.append(left_part.strip())
                expanded.append("..")
                if right_part.strip():
                    expanded.append(right_part.strip())
                expanded.extend(tokens[idx + 1:])
                tokens = expanded
                break
    if ".." not in tokens:
        return None

    sep = tokens.index("..")
    left, right = tokens[:sep], tokens[sep + 1:]
    if len(left) < 2 or not right:
        return None

    # Lewa strona: ostatni token = dolna granica, wcześniejsze = nazwa parametru.
    sensor = " ".join(left[:-1])
    min_val, min_unit = _parse_bound(left[-1])
    min_spec = None if min_val is not None else left[-1]

    # Prawa strona: ostatni numeryczny token = górna granica, etykiety pomijamy.
    max_val, max_unit, max_spec = None, "", None
    for tok in reversed(right):
        candidate, unit = _parse_bound(tok)
        if candidate is not None:
            max_val, max_unit = candidate, unit
            break
    if max_val is None:
        max_spec = right[-1]

    args: dict = {
        "sensor": sensor,
        "min": min_val,
        "max": max_val,
        "unit": max_unit or min_unit or None,
    }
    if min_spec is not None:
        args["min_var"] = min_spec
    if max_spec is not None:
        args["max_var"] = max_spec
    return OqlCmd("CHECK", args, ln, raw)


def parse_IF(rest: str, ln: int, raw: str) -> OqlCmd:
    match = IF_RE.match(rest.strip())
    if match:
        return OqlCmd(
            "CHECK",
            {
                "sensor": match.group(1),
                "min": to_num(match.group(2)),
                "max": to_num(match.group(3)),
                "unit": match.group(4),
            },
            ln,
            raw,
        )

    quoted_range = _parse_if_quoted_range(rest, ln, raw)
    if quoted_range is not None:
        return quoted_range

    cmp_match = IF_CMP_RE.match(rest.strip())
    if cmp_match:
        args: dict = {
            "param": cmp_match.group(1),
            "operator": cmp_match.group(2),
            "value": cmp_match.group(3),
        }
        if cmp_match.group(4) is not None:
            args["or_param"] = cmp_match.group(4)
            args["or_operator"] = cmp_match.group(5)
            args["or_value"] = cmp_match.group(6)
        if cmp_match.group(7):
            args["else_clause"] = cmp_match.group(7).strip()
        return OqlCmd("IF", args, ln, raw)

    raise ValueError(
        f"IF wymaga: sensor min .. max [unit] albo "
        f"'param' <op> 'value' [OR ...] (linia {ln})"
    )


def _make_minmax_parser(cmd: str):
    """Factory: require sensor + value [unit], return OqlCmd(cmd, {sensor, value, unit})."""
    def parser(tokens: list[str], ln: int, raw: str) -> OqlCmd:
        _require(tokens, 2, cmd, ln, "sensor value [unit]")
        sensor = tokens[0]
        value_tokens = tokens[1:]
        if len(value_tokens) == 1 and re.search(r"\s", value_tokens[0]):
            # quoted combined form: MIN 'sensor' '48 mbar'
            value_tokens = value_tokens[0].split()
        value, unit = _split_value_unit(value_tokens)
        return OqlCmd(cmd, {"sensor": sensor, "value": value, "unit": unit}, ln, raw)
    return parser


parse_MIN = _make_minmax_parser("MIN")
parse_MAX = _make_minmax_parser("MAX")


def parse_SAMPLE(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 2, "SAMPLE", ln, "sensor START|STOP [interval]")
    sensor = tokens[0]
    direction = tokens[1].upper()
    if direction not in {"START", "STOP"}:
        raise ValueError(
            f"SAMPLE: drugi argument musi być START lub STOP (linia {ln})"
        )
    interval_ms: Optional[int] = None
    if len(tokens) > 2:
        interval_ms = duration_to_ms(tokens[2])
    return OqlCmd(
        "SAMPLE",
        {"sensor": sensor, "direction": direction, "interval_ms": interval_ms},
        ln,
        raw,
    )


def _make_message_parser(cmd: str):
    """Factory: join all tokens as a message, return OqlCmd(cmd, {message})."""
    def parser(tokens: list[str], ln: int, raw: str) -> OqlCmd:
        message = " ".join(tokens)
        return OqlCmd(cmd, {"message": message}, ln, raw)
    return parser


parse_LOG = _make_message_parser("LOG")
parse_ERROR = _make_message_parser("ERROR")
parse_CORRECT = _make_message_parser("CORRECT")


def _make_call_parser(cmd: str, field: str, required_desc: str):
    """Factory: require one token + rest as args, return OqlCmd(cmd, {field, args})."""
    def parser(tokens: list[str], ln: int, raw: str) -> OqlCmd:
        _require(tokens, 1, cmd, ln, required_desc)
        return OqlCmd(cmd, {field: tokens[0], "args": tokens[1:]}, ln, raw)
    return parser


parse_CALL = _make_call_parser("CALL", "macro", "macro-name [args...]")

parse_INCLUDE = _make_single_field_parser("INCLUDE", "path", '"path.oql"')


parse_FUNC_CALL = _make_call_parser("FUNC", "name", '"func-name" [args...]')


def parse_VAL(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 1, "VAL", ln, "param [unit]")
    unit = tokens[1] if len(tokens) > 1 else None
    return OqlCmd("VAL", {"param": tokens[0], "unit": unit}, ln, raw)


def parse_ELSE(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 2, "ELSE", ln, "ERROR|INFO 'message'")
    action = tokens[0].upper()
    if action not in {"ERROR", "INFO"}:
        raise ValueError(
            f"ELSE: pierwszy argument musi być ERROR lub INFO (linia {ln})"
        )
    return OqlCmd(
        "ELSE", {"action": action, "message": " ".join(tokens[1:])}, ln, raw
    )


parse_GOTO = _make_single_field_parser("GOTO", "target", "target")


def _range_bound(tokens: list[str]) -> tuple[float | int, Optional[str], str]:
    """Parse a RANGE bound: ``['4.2', 'mbar']`` or quoted ``['4.2 mbar']``.

    Returns ``(value, unit, spec)`` where ``spec`` is the bound exactly as
    written (np. ``'11.0 bar'``) — lowering zachowuje oryginalny zapis liczby.
    """
    if len(tokens) == 1 and re.search(r"\s", tokens[0]):
        tokens = tokens[0].split()
    value, unit = _split_value_unit(tokens)
    return value, unit, " ".join(tokens)


def parse_RANGE(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    """``RANGE 'param' 'min [unit]' .. 'max [unit]'`` — deklaratywny zakres (v5)."""
    _require(tokens, 4, "RANGE", ln, "'param' 'min [unit]' .. 'max [unit]'")
    sensor = tokens[0]
    try:
        sep = tokens.index("..")
    except ValueError:
        raise ValueError(
            f"RANGE wymaga separatora '..' między granicami "
            f"(np. RANGE 'param' '4.2 mbar' .. '6.0 mbar', linia {ln})"
        ) from None
    lo_tokens = tokens[1:sep]
    hi_tokens = tokens[sep + 1 :]
    if not lo_tokens or not hi_tokens:
        raise ValueError(
            f"RANGE wymaga granicy po obu stronach separatora '..' (linia {ln})"
        )
    try:
        min_value, min_unit, min_spec = _range_bound(lo_tokens)
        max_value, max_unit, max_spec = _range_bound(hi_tokens)
    except ValueError as exc:
        raise ValueError(f"RANGE: nieprawidłowa granica ({exc}, linia {ln})") from exc
    if min_unit and max_unit and min_unit != max_unit:
        raise ValueError(
            f"RANGE: jednostki granic muszą być identyczne "
            f"({min_unit!r} vs {max_unit!r}, linia {ln})"
        )
    unit = min_unit or max_unit
    return OqlCmd(
        "RANGE",
        {
            "sensor": sensor,
            "min": min_value,
            "max": max_value,
            "unit": unit,
            "min_spec": min_spec,
            "max_spec": max_spec,
        },
        ln,
        raw,
    )


_TASK_FIELDS = {"TITLE", "VAL", "PASS", "FAIL"}


def parse_TASK(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    """``TASK`` — instrukcja/dialog operatora (dialekt c2004).

    Dwie formy generowane przez builder scenariuszy w c2004:

    * ``TASK 'param' 'opis'`` — tytuł/opis zadania powiązany z parametrem,
    * ``TASK TITLE|VAL|PASS|FAIL 'msg'`` — pole dialogu zadania.
    """
    _require(tokens, 2, "TASK", ln, "'param' 'opis' | TITLE|VAL|PASS|FAIL 'msg'")
    head = tokens[0].upper()
    if head in _TASK_FIELDS and len(tokens) == 2:
        return OqlCmd(
            "TASK",
            {"field": head.lower(), "message": tokens[1]},
            ln,
            raw,
        )
    return OqlCmd(
        "TASK",
        {"param": tokens[0], "message": " ".join(tokens[1:])},
        ln,
        raw,
    )


def parse_PASS(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    """``PASS 'message'`` — werdykt pozytywny (v5, alias semantyczny CORRECT).

    Toleruje też dialekt c2004 ``PASS 'param' 'message'`` (dwa cytowane
    tokeny): pierwszy to nazwa parametru, drugi to komunikat werdyktu.
    """
    _require(tokens, 1, "PASS", ln, "'message' | 'param' 'message'")
    if len(tokens) == 2:
        return OqlCmd("PASS", {"param": tokens[0], "message": tokens[1]}, ln, raw)
    return OqlCmd("PASS", {"message": " ".join(tokens)}, ln, raw)


def parse_FAIL(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    """``FAIL 'message' [GOTO 'target' | RETRY n]`` — werdykt negatywny (v5).

    Toleruje też dialekt c2004 ``FAIL 'param' 'message'`` (dwa cytowane
    tokeny bez GOTO/RETRY): pierwszy to nazwa parametru, drugi komunikat.
    """
    _require(tokens, 1, "FAIL", ln, "'message' [GOTO 'target' | RETRY n]")
    tail_idx = None
    for idx, token in enumerate(tokens[1:], start=1):
        if token.upper() in {"GOTO", "RETRY"}:
            tail_idx = idx
            break
    if tail_idx is None:
        if len(tokens) == 2:
            return OqlCmd(
                "FAIL", {"param": tokens[0], "message": tokens[1]}, ln, raw
            )
        return OqlCmd("FAIL", {"message": " ".join(tokens)}, ln, raw)

    args: dict = {"message": " ".join(tokens[:tail_idx])}
    keyword = tokens[tail_idx].upper()
    tail = tokens[tail_idx + 1 :]
    if keyword == "GOTO":
        if len(tail) != 1:
            raise ValueError(
                f"FAIL … GOTO wymaga dokładnie jednego celu 'target' (linia {ln})"
            )
        args["goto"] = tail[0]
    else:  # RETRY
        if len(tail) != 1:
            raise ValueError(
                f"FAIL … RETRY wymaga liczby powtórzeń (linia {ln})"
            )
        try:
            count = int(tail[0])
        except ValueError:
            raise ValueError(
                f"FAIL … RETRY wymaga liczby całkowitej, nie {tail[0]!r} (linia {ln})"
            ) from None
        if count < 1:
            raise ValueError(
                f"FAIL … RETRY wymaga liczby dodatniej (linia {ln})"
            )
        args["retry"] = count
    return OqlCmd("FAIL", args, ln, raw)


def parse_REPEAT(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    if not tokens or tokens[0].upper() == "STOP":
        return OqlCmd("REPEAT", {"action": "stop"}, ln, raw)
    return OqlCmd("REPEAT", {"action": "start", "count": tokens[0]}, ln, raw)


def parse_NOOP(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    """Terminatory bloków legacy (``ENDIF``/``FI``) — w płaskim modelu OQL
    ``IF`` jest warunkiem inline, więc terminator nie niesie akcji (no-op)."""
    return OqlCmd("NOOP", {}, ln, raw)


# ── Dispatch table ───────────────────────────────────────────────

def parse_TESTQL(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    """Generyczny parser komend TestQL (API/ASSERT/EXPECT/GUI/recorder).

    Zachowuje surowe tokeny i nazwę komendy — semantykę nadaje adapter
    (``_lower_testql``), kierując rodzinę komendy do handlera runtime.
    """
    stripped = raw.strip()
    command = stripped.split(None, 1)[0].upper() if stripped else ""
    return OqlCmd(
        "TESTQL",
        {"command": command, "tokens": tokens, "raw": raw},
        ln,
        raw,
    )


#: Komendy TestQL (API/GUI/hardware-assert) używane przez scenariusze c2004.
#: Runtime ma handlery api/assert/expect; GUI/recorder lecą jako no-op action.
_TESTQL_COMMANDS: tuple[str, ...] = (
    "API", "API_GET", "API_POST", "API_PUT", "API_DELETE",
    "ASSERT_STATUS", "ASSERT_JSON", "ASSERT_SENSOR", "ASSERT_VALVE",
    "ASSERT_CONTAINS", "ASSERT_VISIBLE", "ASSERT_TEXT",
    "EXPECT_DEVICE",
    "NAVIGATE", "CLICK", "INPUT", "SELECT_DEVICE", "SELECT_INTERVAL",
    "START_TEST", "STEP_COMPLETE", "RECORD_START", "RECORD_STOP",
    # Declarative browser HUI runtime. OqlOS preserves these as TESTQL no-op
    # commands; @semcod/oqlts compiles and executes them in connect-test.
    "HUI_POLL", "HUI_BUTTON", "HUI_HOLD",
    "ALIAS", "RUN", "EMIT", "APPEND_EVENT",
    # Stable process URIs (c2004://<domain>/<resource>/<kind>/<verb>). Same
    # class as RUN/HUI_POLL above — the browser runtime resolves and executes
    # them — but they were left out when the process layer landed, so a
    # scenario using RUN_URI parsed in oqlts and failed here with
    # "nieznana komenda".
    "RUN_URI", "HUI_POLL_URI",
    # Declarative report projection. The browser runtime validates the safe
    # table/key allow-list and persists the immutable protocol JSON artifact;
    # OqlOS preserves the commands so the same file has parser parity.
    "REPORT_TEMPLATE", "REPORT_SOURCE",
)


DISPATCHERS = {
    "SET":     parse_SET,
    "GET":     parse_GET,
    "READ":    parse_GET,    # alias for readability
    "WAIT":    parse_WAIT,
    "TIMER":   parse_WAIT,   # 2026-07 dialect spelling of WAIT/SET WAIT
    "SAVE":    parse_SAVE,
    "TASK":    parse_TASK,   # dialekt c2004: instrukcja/dialog operatora
    "MIN":     parse_MIN,
    "MAX":     parse_MAX,
    "SAMPLE":  parse_SAMPLE,
    "LOG":     parse_LOG,
    "ERROR":   parse_ERROR,
    "CORRECT": parse_CORRECT,
    "CALL":    parse_CALL,
    "INCLUDE": parse_INCLUDE,
    "FUNC":    parse_FUNC_CALL,
    "REPEAT":  parse_REPEAT,
    "IF_DELTA": parse_IF_DELTA,
    "VAL":     parse_VAL,
    "ELSE":    parse_ELSE,
    "GOTO":    parse_GOTO,
    "RANGE":   parse_RANGE,   # v5: deklaratywny zakres (CHECK = alias historyczny)
    "PASS":    parse_PASS,    # v5: alias semantyczny CORRECT
    "FAIL":    parse_FAIL,    # v5: alias semantyczny ERROR (+ GOTO / RETRY)
    "ENDIF":   parse_NOOP,    # terminator legacy bloku IF (no-op w modelu inline)
    "FI":      parse_NOOP,    # alias ENDIF
    **{cmd: parse_TESTQL for cmd in _TESTQL_COMMANDS},
}

#: Ordered list of canonical base commands (used by documentation tests).
BASE_COMMANDS: tuple[str, ...] = (
    "SET", "GET", "WAIT", "SAVE", "CHECK",
    "MIN", "MAX", "SAMPLE",
    "LOG", "ERROR", "CALL", "INCLUDE", "IF_DELTA",
)


# ── Main parser ──────────────────────────────────────────────────

REPEAT_BLOCK_RE = re.compile(r"^(\s*)REPEAT\s+(\d+)\s*:\s*$", re.IGNORECASE)


def _line_indent(line: str) -> int:
    expanded = str(line or "").replace("\t", "    ")
    return len(expanded) - len(expanded.lstrip(" "))


def _expand_repeat_block_lines(lines: list[str]) -> list[str]:
    expanded: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        match = REPEAT_BLOCK_RE.match(line)
        if not match:
            expanded.append(line)
            i += 1
            continue

        repeat_indent = _line_indent(match.group(1))
        count = max(0, int(match.group(2)))
        block: list[str] = []
        j = i + 1
        while j < len(lines):
            candidate = lines[j]
            if candidate.strip() and _line_indent(candidate) <= repeat_indent:
                break
            block.append(candidate)
            j += 1

        if not block:
            expanded.append(line)
            i += 1
            continue

        block_expanded = _expand_repeat_block_lines(block)
        for _ in range(count):
            expanded.extend(block_expanded)
        i = j
    return expanded


def _expand_repeat_blocks(text: str) -> list[str]:
    return _expand_repeat_block_lines((text or "").splitlines())


def _handle_top_level_line(
    doc: "OqlDoc", raw: str, line: str, ln: int
) -> bool:
    """Handle a top-level line (INCLUDE directive or metadata). Returns True if consumed."""
    if line.upper().startswith("INCLUDE "):
        try:
            tokens = tokenize(line.split(None, 1)[1])
            doc.includes.append(parse_INCLUDE(tokens, ln, line))
        except ValueError as exc:
            doc.errors.append(str(exc))
        return True

    meta = META_RE.match(line)
    if meta and not BLOCK_RE.match(line) and not FUNC_INLINE_NAME_RE.match(line):
        key_raw = meta.group(1)
        doc.meta[key_raw.lower()] = meta.group(2).strip().strip("'\"")
        if key_raw not in _KNOWN_META_KEYS:
            doc.warnings.append(
                f"Linia {ln}: nieznane metadane {key_raw!r} — zachowane"
            )
        return True
    return False


def _handle_block_header(
    doc: "OqlDoc", line: str, ln: int, version_info: object
) -> "OqlBlock | None":
    """Parse a block header line. Returns the new block if matched, else None."""
    block = BLOCK_RE.match(line)
    if not block:
        func_inline = FUNC_INLINE_NAME_RE.match(line)
        if func_inline:
            # ``FUNC: nazwa`` — parytet z frontendem c2004: pusty/nazwany blok FUNC.
            name = func_inline.group(1).strip().strip("'\"")
            new_block = OqlBlock(type="FUNC", name=name, line=ln)
            doc.blocks.append(new_block)
            return new_block
        return None
    name = block.group(2).strip() if block.group(2) else ""
    if name.startswith("[") and name.endswith("]"):
        name = name[1:-1].strip()
    block_type = block.group(1).upper()
    if block_type == "EVENT":
        name = name.strip("'\"")
        if not name:
            doc.errors.append(
                f"Linia {ln}: EVENT wymaga nazwy, np. EVENT 'frontend.ready':"
            )
    if block_type == "TEST":
        # New-dialect spelling of a runnable block — downstream consumers
        # (adapter, interpreters) only know GOAL, so normalize here.
        block_type = "GOAL"
    if (
        version_info.effective >= OQL_VERSION_V4
        and block_type == "GOAL"
        and name
    ):
        doc.errors.append(
            f"Linia {ln}: w VERSION: {version_info.effective} "
            f"użyj 'GOAL:' i nazwy przez 'NAME ...' / 'SET NAME ...'"
        )
    new_block = OqlBlock(type=block_type, name=name, line=ln)
    doc.blocks.append(new_block)
    return new_block


def _handle_macro_body_line(line: str, ln: int, current: "OqlBlock") -> None:
    """Append a deferred line to a MACRO/FUNC block body."""
    parts_peek = line.split(None, 2)
    if (
        len(parts_peek) >= 3
        and parts_peek[0].upper() == "SET"
        and parts_peek[1].upper() == "NAME"
    ):
        current.name = parts_peek[2].strip("'\"")
    elif len(parts_peek) >= 2 and parts_peek[0].upper() == "NAME":
        # 2026-07 dialect: bare NAME instead of SET NAME.
        current.name = " ".join(parts_peek[1:]).strip("'\"")
    current.raw_cmds.append((ln, line))


def _handle_set_name(line: str, current: "OqlBlock") -> bool:
    """Handle SET NAME / bare NAME — updates block name. Returns True if consumed."""
    parts = line.split(None, 1)
    head = parts[0].upper()
    if head == "NAME":
        # 2026-07 dialect: ``NAME 'X'`` without the SET prefix.
        tokens = tokenize(parts[1] if len(parts) > 1 else "")
        if not tokens:
            return False
        current.name = " ".join(tokens).strip("'\"")
        return True
    if head != "SET":
        return False
    tokens = tokenize(parts[1] if len(parts) > 1 else "")
    if len(tokens) >= 2 and tokens[0].upper() == "NAME":
        current.name = " ".join(tokens[1:]).strip("'\"")
        return True
    return False


def _handle_modifier_cmd(
    doc: "OqlDoc", line: str, ln: int, cmd: str, rest: str, current: "OqlBlock"
) -> bool:
    """Handle CORRECT/ERROR that modify the previous condition. Returns True if consumed."""
    if cmd not in ("CORRECT", "ERROR"):
        return False
    if not current.cmds:
        return False
    last_cmd = current.cmds[-1]
    if last_cmd.cmd in {"CHECK", "IF_DELTA"}:
        tokens = tokenize(rest)
        message = " ".join(tokens)
        key = "correct_msg" if cmd == "CORRECT" else "error_msg"
        last_cmd.args[key] = message
        return True
    doc.errors.append(
        f"Linia {ln}: {cmd} musi występować bezpośrednio po CHECK lub IF_DELTA"
    )
    return True


def _parse_and_append_command(
    doc: "OqlDoc", line: str, ln: int, cmd: str, rest: str, current: "OqlBlock"
) -> None:
    """Parse a regular command and append it to the current block."""
    try:
        if cmd == "CHECK":
            parsed = parse_CHECK(rest, ln, line)
        elif cmd == "IF":
            parsed = parse_IF(rest, ln, line)
        else:
            handler = DISPATCHERS.get(cmd)
            if handler is None:
                doc.errors.append(f"Linia {ln}: nieznana komenda {cmd!r}")
                return
            tokens = tokenize(rest)
            parsed = handler(tokens, ln, line)
    except ValueError as exc:
        doc.errors.append(str(exc))
        return
    current.cmds.append(parsed)


def _validate_oql_version(doc: "OqlDoc", version_info: object) -> None:
    """Emit doc errors for unsupported or missing OQL version declarations."""
    if not version_info.declared:
        doc.meta["version"] = str(version_info.effective)
        return
    if version_info.declared not in SUPPORTED_OQL_VERSIONS:
        doc.errors.append(
            f"Nieobsługiwana wersja OQL: {version_info.declared} "
            f"(obsługiwane: {', '.join(str(v) for v in SUPPORTED_OQL_VERSIONS)})"
        )
    if (
        version_info.effective >= OQL_VERSION_V4
        and version_info.first_meaningful_line
        and not re.match(
            rf"^VERSION\s*:\s*{version_info.effective}\s*$",
            version_info.first_meaningful_line,
            re.IGNORECASE,
        )
    ):
        line_no = version_info.first_meaningful_line_number or 1
        doc.errors.append(
            f"Linia {line_no}: pierwsza istotna linia musi mieć postać "
            f"'VERSION: {version_info.effective}'"
        )


def _check_unnamed_goals(doc: "OqlDoc", version_info: object) -> None:
    """Report GOAL blocks missing SET NAME in VERSION: >= 4 documents."""
    if version_info.effective < OQL_VERSION_V4:
        return
    for block in doc.blocks:
        if block.type == "GOAL" and not block.name:
            doc.errors.append(
                f"Linia {block.line}: GOAL w VERSION: {version_info.effective} "
                f"wymaga 'NAME ...' / 'SET NAME ...' jako pierwszej komendy"
            )


def parse_oql(text: str, filename: str = "<string>") -> OqlDoc:
    """Parse OQL source into an :class:`OqlDoc`.

    The parser never raises — all problems are collected in
    :pyattr:`OqlDoc.errors` / :pyattr:`OqlDoc.warnings` so higher layers
    can report them uniformly.
    """

    version_info = resolve_oql_version(text)
    doc = OqlDoc(
        filename=filename,
        oql_version=version_info.effective,
        declared_version=version_info.declared,
    )

    _validate_oql_version(doc, version_info)

    current: OqlBlock | None = None

    for ln, raw in enumerate(_expand_repeat_blocks(text), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if GRANT_RE.match(line):
            continue

        if current is None and _handle_top_level_line(doc, raw, line, ln):
            continue

        new_block = _handle_block_header(doc, line, ln, version_info)
        if new_block is not None:
            current = new_block
            continue

        if current is None:
            doc.errors.append(f"Linia {ln}: komenda poza blokiem: {line!r}")
            continue
        if not (raw.startswith(" ") or raw.startswith("\t")):
            doc.errors.append(f"Linia {ln}: komenda musi być wcięta: {line!r}")
            continue

        if current.type in ("MACRO", "FUNC"):
            _handle_macro_body_line(line, ln, current)
            continue

        parts = line.split(None, 1)
        cmd = parts[0].upper()
        rest = parts[1] if len(parts) > 1 else ""

        if _handle_set_name(line, current):
            continue

        if _handle_modifier_cmd(doc, line, ln, cmd, rest, current):
            continue

        _parse_and_append_command(doc, line, ln, cmd, rest, current)

    _check_unnamed_goals(doc, version_info)

    return doc


# ── Smoke-print helpers (CLI debug) ──────────────────────────────


def format_doc(doc: OqlDoc) -> str:
    """Pretty-print for ad-hoc debugging."""

    lines: list[str] = []
    if doc.meta:
        lines.append("META:")
        for key, value in doc.meta.items():
            lines.append(f"  {key} = {value}")
        lines.append("")
    for block in doc.blocks:
        lines.append(f"{block.type} {block.name}:")
        for cmd in block.cmds:
            lines.append(f"  {cmd}")
        lines.append("")
    if doc.errors:
        lines.append("ERRORS:")
        for err in doc.errors:
            lines.append(f"  ✗ {err}")
    if doc.warnings:
        lines.append("WARNINGS:")
        for warn in doc.warnings:
            lines.append(f"  ! {warn}")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover — manual smoke test
    import sys

    SAMPLE = """
VERSION: 4
SCENARIO: Przykładowy test maski
DEVICE: BA / PSS 7000 / Dräger

CONFIG reset:
  SET pompa-1 0
  SET zawór-sc 0
  SET WAIT '500 ms'

GOAL:
  SET NAME [test-ciśnienia]
  SET pompa-1 5.0 l/min
  SET WAIT '3 s'
  GET AI02
  CHECK 6.0 <= AI02 <= 8.0 bar
  SAVE ciśnienie-sc

GOAL:
  SET NAME [test z spacjami]
  SET [pompa głównego obiegu] 5.0 l/min
  SET WAIT '1 s'
"""
    target = sys.argv[1] if len(sys.argv) > 1 else None
    source = open(target, encoding="utf-8").read() if target else SAMPLE
    print(format_doc(parse_oql(source, target or "<sample>")))
