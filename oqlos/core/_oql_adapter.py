"""Adapter: convert :class:`OqlDoc` produced by ``oql_parser`` into the
existing :class:`CqlDocument` AST consumed by the runtime interpreter.

This keeps the new v3 flat OQL grammar fully executable by reusing the
mature action/condition handlers in ``_interpreter_actions.py`` without
touching them.

The adapter also performs two lightweight transformations:

* ``INCLUDE "file.oql"`` — inlines macro libraries from adjacent files
  (search order: absolute path, path relative to the including file,
  path relative to ``oqlos/scenarios``).
* ``CALL name [args]`` — expands registered ``MACRO`` bodies; extra
  positional tokens after the name are substituted as ``$1``, ``$2``…
  inside the macro body (string replacement on the raw argument text).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

from oqlos.models.dsl_models import (
    CqlAction,
    CqlCondition,
    CqlDocument,
    CqlGoal,
    CqlMetadata,
    CqlStep,
)

from .oql_parser import (
    DISPATCHERS,
    OqlBlock,
    OqlCmd,
    OqlDoc,
    parse_CHECK,
    parse_oql,
    tokenize,
)


# ── Helpers ──────────────────────────────────────────────────────


def _fmt_value(value, unit) -> str:
    if unit:
        return f"{value} {unit}"
    return str(value)


def _scenarios_root() -> Path:
    """Default search root for ``INCLUDE`` directives."""
    return Path(__file__).resolve().parent.parent / "scenarios"


def _resolve_include(path: str, base: Path | None) -> Path | None:
    """Try to find an included file relative to common locations."""
    candidate = Path(path)
    if candidate.is_absolute() and candidate.is_file():
        return candidate
    roots: list[Path] = []
    if base is not None:
        roots.append(base.parent)
    roots.append(_scenarios_root())
    for root in roots:
        hit = (root / path).resolve()
        if hit.is_file():
            return hit
    return None


def _substitute_args(raw: str, args: list[str]) -> str:
    """Substitute ``$1``, ``$2``… placeholders in ``raw``."""
    if not args:
        return raw
    result = raw
    for idx, value in enumerate(args, start=1):
        result = re.sub(rf"\${idx}\b", value, result)
    return result


# ── Macro registry + INCLUDE resolution ──────────────────────────


class _MacroRegistry:
    """Collect ``MACRO`` definitions (raw body lines) from the root
    document plus includes.  Bodies are parsed lazily after ``$N``
    substitution at expansion time.
    """

    def __init__(self) -> None:
        self._macros: dict[str, list[tuple[int, str]]] = {}

    def register(self, block: OqlBlock) -> None:
        self._macros[block.name] = list(block.raw_cmds)

    def get(self, name: str) -> list[tuple[int, str]] | None:
        return self._macros.get(name)


def _load_includes(
    doc: OqlDoc,
    macros: _MacroRegistry,
    base: Path | None,
    seen: set[Path],
) -> None:
    """Recursively inline INCLUDE directives and register their macros."""

    pending: list[OqlCmd] = list(doc.includes)
    for block in doc.blocks:
        for cmd in block.cmds:
            if cmd.cmd == "INCLUDE":
                pending.append(cmd)

    for cmd in pending:
        path = cmd.args.get("path", "")
        resolved = _resolve_include(path, base)
        if resolved is None:
            doc.errors.append(
                f"INCLUDE {path!r}: nie znaleziono pliku (linia {cmd.line})"
            )
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            sub_source = resolved.read_text(encoding="utf-8")
        except OSError as exc:
            doc.errors.append(f"INCLUDE {path!r}: {exc}")
            continue
        sub_doc = parse_oql(sub_source, str(resolved))
        _load_includes(sub_doc, macros, resolved, seen)
        for block in sub_doc.blocks:
            if block.type == "MACRO":
                macros.register(block)
        doc.errors.extend(sub_doc.errors)
        doc.warnings.extend(sub_doc.warnings)

    # Register macros defined in the current document (after includes so
    # local definitions can override library ones).
    for block in doc.blocks:
        if block.type == "MACRO":
            macros.register(block)


# ── OQL command → CqlAction ──────────────────────────────────────


def _cmd_to_actions(
    cmd: OqlCmd, macros: _MacroRegistry, visiting: tuple[str, ...] = ()
) -> list[CqlAction]:
    """Lower a single OQL command to zero or more CqlActions."""

    kind = cmd.cmd

    if kind == "INCLUDE":
        # already inlined by _load_includes; skip at call sites
        return []

    if kind == "CALL":
        macro_name = cmd.args["macro"]
        args = list(cmd.args.get("args") or [])
        body = macros.get(macro_name)
        if body is None:
            return [
                CqlAction(
                    kind="error",
                    args=f"Nieznane makro: {macro_name}",
                    raw=cmd.raw,
                )
            ]
        if macro_name in visiting:
            return [
                CqlAction(
                    kind="error",
                    args=f"Rekurencyjne makro: {macro_name}",
                    raw=cmd.raw,
                )
            ]
        expanded: list[CqlAction] = []
        for ln, raw_line in body:
            inner = _parse_macro_line(raw_line, ln, args)
            if inner is None:
                expanded.append(
                    CqlAction(
                        kind="error",
                        args=f"Makro {macro_name!r}: błąd linii {ln}: {raw_line!r}",
                        raw=raw_line,
                    )
                )
                continue
            expanded.extend(
                _cmd_to_actions(inner, macros, visiting + (macro_name,))
            )
        return expanded

    if kind == "SET":
        target = cmd.args["target"]
        raw_value = _fmt_value(cmd.args["value"], cmd.args.get("unit"))
        return [
            CqlAction(
                kind="set",
                target=target,
                args=raw_value,
                raw=cmd.raw,
            )
        ]

    if kind == "GET":
        sensor = cmd.args["sensor"]
        return [
            CqlAction(kind="val", target=sensor, args="", raw=cmd.raw)
        ]

    if kind == "WAIT":
        token = cmd.args.get("raw") or f"{cmd.args.get('ms', 0)}ms"
        return [
            CqlAction(kind="wait", args=token, raw=cmd.raw)
        ]

    if kind == "SAVE":
        return [
            CqlAction(
                kind="save",
                target=cmd.args["label"],
                raw=cmd.raw,
            )
        ]

    if kind == "MIN":
        args = _fmt_value(cmd.args["value"], cmd.args.get("unit"))
        return [
            CqlAction(
                kind="min",
                target=cmd.args["sensor"],
                args=args,
                raw=cmd.raw,
            )
        ]

    if kind == "MAX":
        args = _fmt_value(cmd.args["value"], cmd.args.get("unit"))
        return [
            CqlAction(
                kind="max",
                target=cmd.args["sensor"],
                args=args,
                raw=cmd.raw,
            )
        ]

    if kind == "CHECK":
        # Use custom messages if provided via CORRECT/ERROR, otherwise defaults
        default_fail = (
            f"{cmd.args['sensor']} poza zakresem "
            f"[{cmd.args['min']}, {cmd.args['max']}] "
            f"{cmd.args.get('unit') or ''}".strip()
        )
        cond = CqlCondition(
            sensor=cmd.args["sensor"],
            operator="∈",
            value_min=cmd.args["min"],
            value_max=cmd.args["max"],
            unit=cmd.args.get("unit") or "",
            on_fail="ERROR",
            fail_message=cmd.args.get("error_msg") or default_fail,
            pass_message=cmd.args.get("correct_msg") or "",
        )
        return [
            CqlAction(
                kind="condition",
                condition=cond,
                raw=cmd.raw,
            )
        ]

    if kind == "SAMPLE":
        direction = cmd.args["direction"]
        interval = cmd.args.get("interval_ms")
        args = direction if interval is None else f"{direction} {interval}ms"
        return [
            CqlAction(
                kind="sample",
                target=cmd.args["sensor"],
                method=direction,
                args=args,
                raw=cmd.raw,
            )
        ]

    if kind == "LOG":
        return [
            CqlAction(kind="log", args=cmd.args.get("message", ""), raw=cmd.raw)
        ]

    if kind == "ERROR":
        return [
            CqlAction(kind="error", args=cmd.args.get("message", ""), raw=cmd.raw)
        ]

    # Fallback — unknown but structurally valid command
    return [CqlAction(kind="action", method=kind, raw=cmd.raw)]


def _parse_macro_line(
    raw_line: str, ln: int, args: list[str]
) -> OqlCmd | None:
    """Parse a single macro body line after substituting ``$N`` placeholders.

    Returns ``None`` when the line cannot be parsed.
    """
    substituted = _substitute_args(raw_line.strip(), args)
    if not substituted or substituted.startswith("#"):
        return None

    parts = substituted.split(None, 1)
    if not parts:
        return None
    cmd_name = parts[0].upper()
    rest = parts[1] if len(parts) > 1 else ""

    try:
        if cmd_name == "CHECK":
            return parse_CHECK(rest, ln, substituted)
        handler = DISPATCHERS.get(cmd_name)
        if handler is None:
            return None
        tokens = tokenize(rest)
        return handler(tokens, ln, substituted)
    except ValueError:
        return None


# ── Public entrypoint ────────────────────────────────────────────


def is_flat_oql(source: str) -> bool:
    """Heuristic: detect new-style (v3) flat OQL source.

    Returns ``True`` when the text uses ``GOAL name:`` / ``CONFIG name:`` /
    ``MACRO name:`` block headers (with the colon AFTER the name), as
    opposed to the legacy ``GOAL:`` (colon immediately after the keyword).
    A top-level ``INCLUDE "..."`` directive also triggers the new grammar.
    """

    block_re = re.compile(r"^\s*(GOAL|CONFIG|MACRO)\s+[^\s:][^:]*:\s*$", re.M)
    legacy_re = re.compile(r"^\s*(GOAL|CONFIG)\s*:\s*\S", re.M)
    include_re = re.compile(r"^\s*INCLUDE\s+[\"']", re.M)

    has_new = bool(block_re.search(source) or include_re.search(source))
    has_legacy = bool(legacy_re.search(source))
    if has_new and not has_legacy:
        return True
    # If both patterns appear, treat as legacy (safer fallback).
    return has_new and not has_legacy


def oql_doc_to_cql(doc: OqlDoc) -> CqlDocument:
    """Convert a parsed :class:`OqlDoc` into a :class:`CqlDocument`."""

    base = Path(doc.filename).resolve() if doc.filename and doc.filename != "<string>" else None
    macros = _MacroRegistry()
    _load_includes(doc, macros, base, seen=set())

    metadata = CqlMetadata(
        scenario_name=doc.meta.get("scenario", ""),
        device_type=doc.meta.get("device_type", "") or _split_device_field(doc.meta.get("device", ""), 0),
        device_model=doc.meta.get("device_model", "") or _split_device_field(doc.meta.get("device", ""), 1),
        manufacturer=doc.meta.get("manufacturer", "") or _split_device_field(doc.meta.get("device", ""), 2),
    )

    cdoc = CqlDocument(filename=doc.filename, metadata=metadata)
    cdoc.errors.extend(doc.errors)
    cdoc.warnings.extend(doc.warnings)

    # CONFIG blocks run first (initialization), then GOAL blocks.
    # MACRO blocks are registered but never executed directly.
    ordered_blocks: list[OqlBlock] = [
        b for b in doc.blocks if b.type == "CONFIG"
    ] + [
        b for b in doc.blocks if b.type == "GOAL"
    ]

    for block in ordered_blocks:
        actions: list[CqlAction] = []
        for cmd in block.cmds:
            actions.extend(_cmd_to_actions(cmd, macros))
        goal_name = block.name
        if block.type == "CONFIG":
            goal_name = f"[CONFIG] {block.name}"
        step = CqlStep(number="1", name=block.name, actions=actions)
        cdoc.goals.append(
            CqlGoal(name=goal_name, description="", steps=[step])
        )

    return cdoc


def _split_device_field(device: str, index: int) -> str:
    """Split ``BA / PSS 7000 / Dräger`` on ``/`` and pick a component."""
    if not device:
        return ""
    parts = [p.strip() for p in device.split("/")]
    return parts[index] if index < len(parts) else ""


def parse_flat_oql(source: str, filename: str = "<string>") -> CqlDocument:
    """Convenience: parse flat OQL directly to a :class:`CqlDocument`."""
    return oql_doc_to_cql(parse_oql(source, filename))
