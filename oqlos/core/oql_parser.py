"""
OQL v3 parser — flat, quote-free syntax based on TODO/oql_parser.py.

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
from typing import Any, Optional

# ── Regex building blocks ─────────────────────────────────────────

#: Numeric literal (int or float, optional sign).
NUM = r"-?\d+(?:[.,]\d+)?"

#: Duration: number optionally glued to a time unit (``3s``, ``500ms``, ``3000``).
DUR_RE = re.compile(rf"^({NUM})(ms|s|m|h)?$")

#: Header of a block: ``GOAL name:``, ``CONFIG name:``, ``MACRO name:``.
BLOCK_RE = re.compile(r"^(GOAL|CONFIG|MACRO)(?:\s+(.+?))?:\s*$", re.IGNORECASE)

#: Metadata line: ``KEY: value`` (KEY is UPPER_SNAKE).
META_RE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*:\s*(.+)$")

#: ``CHECK`` clause: ``min <= sensor <= max unit``.
CHECK_RE = re.compile(
    rf"^({NUM})\s*<=\s*(\S+)\s*<=\s*({NUM})(?:\s+(\S+))?$"
)

#: ``IF`` range clause: ``sensor min .. max [unit]``.
IF_RE = re.compile(
    rf"^(\S+)\s+({NUM})\s*\.\.\s*({NUM})(?:\s+(\S+))?$"
)

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

    # Convenience helpers ---------------------------------------------------

    def goals(self) -> list[OqlBlock]:
        return [b for b in self.blocks if b.type == "GOAL"]

    def configs(self) -> list[OqlBlock]:
        return [b for b in self.blocks if b.type == "CONFIG"]

    def macros(self) -> list[OqlBlock]:
        return [b for b in self.blocks if b.type == "MACRO"]


# ── Conversion helpers ───────────────────────────────────────────


def to_num(raw: str) -> float | int:
    """Convert '6.0' → 6.0, '3' → 3, '-10,5' → -10.5 (accepts comma)."""
    value = float(str(raw).replace(",", "."))
    return int(value) if value == int(value) else value


def parse_duration(token: str) -> tuple[float | int, str]:
    """Parse ``3s``, ``500ms``, ``3000`` (bare number defaults to ``ms``)."""
    match = DUR_RE.match(token)
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


def parse_SET(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 2, "SET", ln, "target value [unit]")
    target = tokens[0]
    value, unit = _split_value_unit(tokens[1:])
    return OqlCmd("SET", {"target": target, "value": value, "unit": unit}, ln, raw)


def parse_GET(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 1, "GET", ln, "sensor")
    return OqlCmd("GET", {"sensor": tokens[0]}, ln, raw)


def parse_WAIT(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 1, "WAIT", ln, "duration")
    value, unit = parse_duration(tokens[0])
    ms = duration_to_ms(tokens[0])
    return OqlCmd(
        "WAIT",
        {"ms": ms, "value": value, "unit": unit, "raw": tokens[0]},
        ln,
        raw,
    )


def parse_SAVE(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 1, "SAVE", ln, "label")
    return OqlCmd("SAVE", {"label": tokens[0]}, ln, raw)


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


def parse_IF(rest: str, ln: int, raw: str) -> OqlCmd:
    match = IF_RE.match(rest.strip())
    if not match:
        raise ValueError(
            f"IF wymaga: sensor min .. max [unit] (linia {ln})"
        )
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


def parse_MIN(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 2, "MIN", ln, "sensor value [unit]")
    sensor = tokens[0]
    value, unit = _split_value_unit(tokens[1:])
    return OqlCmd("MIN", {"sensor": sensor, "value": value, "unit": unit}, ln, raw)


def parse_MAX(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 2, "MAX", ln, "sensor value [unit]")
    sensor = tokens[0]
    value, unit = _split_value_unit(tokens[1:])
    return OqlCmd("MAX", {"sensor": sensor, "value": value, "unit": unit}, ln, raw)


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


def parse_LOG(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    message = " ".join(tokens)
    return OqlCmd("LOG", {"message": message}, ln, raw)


def parse_ERROR(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    message = " ".join(tokens)
    return OqlCmd("ERROR", {"message": message}, ln, raw)


def parse_CORRECT(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    message = " ".join(tokens)
    return OqlCmd("CORRECT", {"message": message}, ln, raw)


def parse_CALL(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 1, "CALL", ln, "macro-name [args...]")
    return OqlCmd("CALL", {"macro": tokens[0], "args": tokens[1:]}, ln, raw)


def parse_INCLUDE(tokens: list[str], ln: int, raw: str) -> OqlCmd:
    _require(tokens, 1, "INCLUDE", ln, '"path.oql"')
    return OqlCmd("INCLUDE", {"path": tokens[0]}, ln, raw)


# ── Dispatch table ───────────────────────────────────────────────

DISPATCHERS = {
    "SET":     parse_SET,
    "GET":     parse_GET,
    "READ":    parse_GET,    # alias for readability
    "WAIT":    parse_WAIT,
    "SAVE":    parse_SAVE,
    "MIN":     parse_MIN,
    "MAX":     parse_MAX,
    "SAMPLE":  parse_SAMPLE,
    "LOG":     parse_LOG,
    "ERROR":   parse_ERROR,
    "CORRECT": parse_CORRECT,
    "CALL":    parse_CALL,
    "INCLUDE": parse_INCLUDE,
}

#: Ordered list of canonical base commands (used by documentation tests).
BASE_COMMANDS: tuple[str, ...] = (
    "SET", "GET", "WAIT", "SAVE", "CHECK",
    "MIN", "MAX", "SAMPLE",
    "LOG", "ERROR", "CALL", "INCLUDE",
)


# ── Main parser ──────────────────────────────────────────────────


def parse_oql(text: str, filename: str = "<string>") -> OqlDoc:
    """Parse OQL source into an :class:`OqlDoc`.

    The parser never raises — all problems are collected in
    :pyattr:`OqlDoc.errors` / :pyattr:`OqlDoc.warnings` so higher layers
    can report them uniformly.
    """

    doc = OqlDoc(filename=filename)
    current: OqlBlock | None = None

    for ln, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()

        # blank / comment
        if not line or line.startswith("#"):
            continue

        # top-level metadata (``KEY: value``) — only when not inside a block
        if current is None:
            # ``INCLUDE "path"`` is allowed at the top level (outside blocks)
            # because it affects the whole document.
            if line.upper().startswith("INCLUDE "):
                try:
                    tokens = tokenize(line.split(None, 1)[1])
                    doc.includes.append(parse_INCLUDE(tokens, ln, line))
                except ValueError as exc:
                    doc.errors.append(str(exc))
                continue

            meta = META_RE.match(line)
            if meta and not BLOCK_RE.match(line):
                key_raw = meta.group(1)
                if key_raw in _KNOWN_META_KEYS:
                    doc.meta[key_raw.lower()] = meta.group(2).strip().strip("'\"")
                    continue
                # unknown metadata key — keep it, but warn
                doc.meta[key_raw.lower()] = meta.group(2).strip().strip("'\"")
                doc.warnings.append(
                    f"Linia {ln}: nieznane metadane {key_raw!r} — zachowane"
                )
                continue

        # block header
        block = BLOCK_RE.match(line)
        if block:
            name = block.group(2).strip() if block.group(2) else ""
            # allow ``GOAL [Nazwa ze spacjami]:`` form
            if name.startswith("[") and name.endswith("]"):
                name = name[1:-1].strip()
            current = OqlBlock(
                type=block.group(1).upper(),
                name=name,
                line=ln,
            )
            doc.blocks.append(current)
            continue

        # command line must be indented inside a block
        if current is None:
            doc.errors.append(f"Linia {ln}: komenda poza blokiem: {line!r}")
            continue
        if not (raw.startswith(" ") or raw.startswith("\t")):
            doc.errors.append(f"Linia {ln}: komenda musi być wcięta: {line!r}")
            continue

        # Inside MACRO blocks, defer parsing — the body may contain $N
        # placeholders that are only resolvable at expansion time.
        if current.type == "MACRO":
            current.raw_cmds.append((ln, line))
            continue

        parts = line.split(None, 1)
        cmd = parts[0].upper()
        rest = parts[1] if len(parts) > 1 else ""

        # SET NAME updates the current block name (metadata only)
        if cmd == "SET" and current:
            tokens = tokenize(rest)
            if len(tokens) >= 2 and tokens[0].upper() == "NAME":
                current.name = " ".join(tokens[1:]).strip("'\"")
                continue  # Don't add as a regular command

        # CORRECT and ERROR modify the previous CHECK command
        if cmd in ("CORRECT", "ERROR") and current.cmds:
            last_cmd = current.cmds[-1]
            if last_cmd.cmd == "CHECK":
                tokens = tokenize(rest)
                message = " ".join(tokens)
                key = "correct_msg" if cmd == "CORRECT" else "error_msg"
                last_cmd.args[key] = message
                continue
            else:
                doc.errors.append(
                    f"Linia {ln}: {cmd} musi występować bezpośrednio po CHECK"
                )
                continue

        try:
            if cmd == "CHECK":
                parsed = parse_CHECK(rest, ln, line)
            elif cmd == "IF":
                parsed = parse_IF(rest, ln, line)
            else:
                handler = DISPATCHERS.get(cmd)
                if handler is None:
                    doc.errors.append(
                        f"Linia {ln}: nieznana komenda {cmd!r}"
                    )
                    continue
                tokens = tokenize(rest)
                parsed = handler(tokens, ln, line)
        except ValueError as exc:
            doc.errors.append(str(exc))
            continue

        current.cmds.append(parsed)

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
SCENARIO: Przykładowy test maski
DEVICE: BA / PSS 7000 / Dräger

CONFIG reset:
  SET pompa-1 0
  SET zawór-sc 0
  WAIT 500ms

GOAL test-ciśnienia:
  SET pompa-1 5.0 l/min
  WAIT 3s
  GET AI02
  CHECK 6.0 <= AI02 <= 8.0 bar
  SAVE ciśnienie-sc

GOAL [test z spacjami]:
  SET [pompa głównego obiegu] 5.0 l/min
  WAIT 1s
"""
    target = sys.argv[1] if len(sys.argv) > 1 else None
    source = open(target, encoding="utf-8").read() if target else SAMPLE
    print(format_doc(parse_oql(source, target or "<sample>")))
