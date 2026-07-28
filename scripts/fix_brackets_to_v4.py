#!/usr/bin/env python3
"""Convert local .oql files with v2 bracket syntax [...] to v4."""

import argparse
import re
import sys
from pathlib import Path

# Import migration function from existing script
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.oql_v2_to_v4_migrate_db import migrate_v2_to_v4


def needs_migration(text: str) -> bool:
    """Check if text contains v2 bracket syntax, legacy MIN/MAX, PUMP, or old IF sentinels."""
    if re.search(r"\[([^\]]+)\]", text):
        return True
    if re.search(r"^\s*(MIN|MAX)\s+\S+\s*[= ]", text, re.MULTILINE | re.IGNORECASE):
        return True
    if re.search(r"^\s*PUMP\s+\S", text, re.MULTILINE | re.IGNORECASE):
        return True
    if re.search(r"\.\.\s*(999999|-999999|\s*999999)", text):
        return True
    if re.search(r"-999999\s*\.\.", text):
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Convert v2 bracket syntax to v4 in local .oql files")
    parser.add_argument("--root", default="oql-scenario/", help="Root directory to search for .oql files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"Error: {root} is not a directory")
        sys.exit(1)

    oql_files = list(root.glob("*.oql"))
    if not oql_files:
        print(f"No .oql files found in {root}")
        sys.exit(0)

    print(f"🔍 Szukam plików .oql w: {root.absolute()}")
    print(f"Znaleziono {len(oql_files)} plików .oql\n")

    to_migrate = []
    for f in oql_files:
        try:
            content = f.read_text(encoding="utf-8")
            if needs_migration(content):
                to_migrate.append(f)
        except Exception as e:
            print(f"❌ Błąd odczytu {f.name}: {e}")

    if not to_migrate:
        print("✅ Żaden plik nie wymaga migracji")
        sys.exit(0)

    print(f"📊 Znaleziono {len(to_migrate)} plików do migracji:\n")
    for f in to_migrate:
        print(f"  - {f.name}")

    if args.dry_run:
        print("\n🔍 DRY-RUN - nie wprowadzam zmian")
        for f in to_migrate:
            content = f.read_text(encoding="utf-8")
            migrated = migrate_v2_to_v4(content)
            if content != migrated:
                print(f"\n  {f.name}:")
                print("  --- PRZED ---")
                print(content)
                print("  --- PO ---")
                print(migrated)
        sys.exit(0)

    print("\n🔄 Migrowanie plików...")
    for f in to_migrate:
        try:
            content = f.read_text(encoding="utf-8")
            migrated = migrate_v2_to_v4(content)
            if content != migrated:
                f.write_text(migrated, encoding="utf-8")
                print(f"  ✅ {f.name} - zaktualizowano")
            else:
                print(f"  ℹ️  {f.name} - bez zmian")
        except Exception as e:
            print(f"  ❌ {f.name} - błąd: {e}")

    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    main()
