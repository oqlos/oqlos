"""Offline validation, conversion, and legacy migration for hardware config."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from oqlos.hardware.configuration import (
    HardwareConfigurationError,
    detect_hardware_configuration_format,
    load_hardware_configuration,
    parse_hardware_configuration,
    resolve_effective_hardware_configuration,
    save_hardware_configuration,
    semantic_configuration_diff,
    serialize_hardware_configuration,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oqlos-hardware-config")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "effective"):
        command = commands.add_parser(name)
        command.add_argument("source")
    convert = commands.add_parser("convert")
    convert.add_argument("source")
    convert.add_argument("target")
    convert.add_argument("--force", action="store_true")
    migrate = commands.add_parser("migrate-legacy")
    migrate.add_argument("source")
    migrate.add_argument("target")
    migrate.add_argument("--force", action="store_true")
    return parser


def _write_target(source: Path, target: Path, *, allow_legacy: bool, force: bool) -> dict:
    if target.exists() and not force:
        raise HardwareConfigurationError(f"target already exists: {target}; pass --force to replace")
    source_format = detect_hardware_configuration_format(source)
    content = source.read_text(encoding="utf-8")
    config = parse_hardware_configuration(
        content,
        source_format,
        source=str(source),
        allow_legacy=allow_legacy,
    )
    target_format = detect_hardware_configuration_format(target)
    save_hardware_configuration(target, config, format=target_format)
    return {
        "ok": True,
        "source": str(source),
        "source_format": source_format,
        "target": str(target),
        "target_format": target_format,
        "contract": config.schema_version,
        "legacy_migration": allow_legacy,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        source = Path(args.source).expanduser()
        if args.command == "validate":
            config = load_hardware_configuration(source, allow_legacy=False)
            result = {"ok": True, "source": str(source), "contract": config.schema_version}
        elif args.command == "effective":
            config = load_hardware_configuration(source, allow_legacy=False)
            effective, overrides = resolve_effective_hardware_configuration(config)
            result = {
                "ok": True,
                "source": str(source),
                "configured": config.canonical_dict(),
                "effective": effective.canonical_dict(),
                "overrides": overrides,
                "diff": semantic_configuration_diff(config, effective),
            }
        elif args.command == "convert":
            result = _write_target(
                source,
                Path(args.target).expanduser(),
                allow_legacy=False,
                force=args.force,
            )
        else:
            result = _write_target(
                source,
                Path(args.target).expanduser(),
                allow_legacy=True,
                force=args.force,
            )
    except (HardwareConfigurationError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
