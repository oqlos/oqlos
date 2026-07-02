#!/usr/bin/env python3
"""Masowa migracja plików .oql do VERSION: 4.

Ten skrypt:
1. Znajduje wszystkie pliki .oql w repo
2. Sprawdza czy mają VERSION: 4
3. Jeśli nie - stosuje transformacje migracyjne
4. Generuje raport
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional

# Dodaj parent dir do path żeby importować oqlos
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from oqlos.core.oql_versioning import OQL_VERSION_CURRENT
from oqlos.tools.cql_cli.formatting import _quote_oql, canonicalize_oql_text


def find_oql_files(root_dir: Path) -> list[Path]:
    """Znajdź wszystkie pliki .oql poza venv/.venv."""
    files = []
    for path in root_dir.rglob("*.oql"):
        # Pomiń venv
        if "venv" in str(path) or ".venv" in str(path):
            continue
        # Pomiń katalogi systemowe
        if any(part.startswith(".") for part in path.parts[:-1]):
            continue
        files.append(path)
    return sorted(files)


def has_version_header(content: str) -> bool:
    """Sprawdź czy plik ma nagłówek VERSION: X."""
    lines = content.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return bool(re.match(r"^VERSION\s*:\s*\d+", stripped, re.IGNORECASE))
    return False


def extract_version(content: str) -> Optional[int]:
    """Wyciągnij numer wersji z pliku."""
    lines = content.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            match = re.match(r"^VERSION\s*:\s*(\d+)", stripped, re.IGNORECASE)
            if match:
                return int(match.group(1))
    return None


def _migrate_version_header(content: str) -> tuple[list[str], list[str]]:
    """Return prefix lines and change log if VERSION header is missing."""
    if not has_version_header(content):
        return [f"VERSION: {OQL_VERSION_CURRENT}"], ["Dodano VERSION: 4 na początku"]
    return [], []


def _migrate_goal_line(line: str, stripped: str) -> tuple[list[str] | None, str | None]:
    """Transform GOAL: Name -> GOAL: + SET NAME 'Name'. Returns (new_lines, change) or (None, None)."""
    goal_match = re.match(r"^(GOAL)\s*:\s*(.+?)\s*$", stripped, re.IGNORECASE)
    if not goal_match:
        return None, None
    goal_name = goal_match.group(2).strip()
    if (goal_name.startswith('"') and goal_name.endswith('"')) or \
       (goal_name.startswith("'") and goal_name.endswith("'")):
        goal_name = goal_name[1:-1]
    return ["GOAL:", f"  SET NAME {_quote_oql(goal_name)}"], f"GOAL: {goal_match.group(2)} -> GOAL: + SET NAME"


def _migrate_loop_line(line: str, stripped: str) -> tuple[str | None, str | None]:
    """Transform LOOP N TIMES -> REPEAT N:. Returns (new_line, change) or (None, None)."""
    if not re.match(r"^LOOP\b", stripped, re.IGNORECASE):
        return None, None
    loop_match = re.match(r"^LOOP\s+(\d+)\s+TIMES\s*$", stripped, re.IGNORECASE)
    if loop_match:
        count = loop_match.group(1)
        return f"REPEAT {count}:", f"LOOP {count} TIMES -> REPEAT {count}:"
    return line, None


def _migrate_endloop_line(stripped: str) -> tuple[str | None, str | None]:
    """Transform ENDLOOP -> REPEAT STOP. Returns (new_line, change) or (None, None)."""
    if re.match(r"^ENDLOOP\s*$", stripped, re.IGNORECASE):
        return "REPEAT STOP", "ENDLOOP -> REPEAT STOP"
    return None, None


def _migrate_set_line(line: str, stripped: str) -> tuple[str | None, None]:
    """Normalize canonical SET 'x' 'y' syntax. Returns (new_line, None) or (None, None)."""
    set_match = re.match(r"^SET\s+['\"]([^'\"]+)['\"]\s+['\"]([^'\"]+)['\"](.*)$", stripped, re.IGNORECASE)
    if set_match:
        return (
            f"  SET {_quote_oql(set_match.group(1))} {_quote_oql(set_match.group(2))}{set_match.group(3)}",
            None,
        )
    return None, None


def _migrate_simple_quoted_line(stripped: str, keyword: str) -> tuple[str | None, str | None]:
    """Transform KEYWORD 'x' -> KEYWORD x. Returns (new_line, change) or (None, None)."""
    m = re.match(rf"^{keyword}\s+['\"](.+?)['\"]\s*$", stripped, re.IGNORECASE)
    if m:
        value = m.group(1)
        return f"  {keyword} {value}", f"{keyword} '{value}' -> {keyword} {value}"
    return None, None


def _migrate_wait_line(stripped: str) -> tuple[str | None, str | None]:
    """Transform WAIT 'X' -> WAIT X. Returns (new_line, change) or (None, None)."""
    return _migrate_simple_quoted_line(stripped, "WAIT")


def _migrate_minmax_line(stripped: str) -> tuple[str | None, str | None]:
    """Transform MIN/MAX 'sensor' 'value' -> MIN/MAX sensor value."""
    minmax_match = re.match(
        r"^(MIN|MAX)\s+['\"]([^'\"]+)['\"]\s+['\"]([^'\"]+)['\"](.*)$", stripped, re.IGNORECASE
    )
    if not minmax_match:
        return None, None
    cmd = minmax_match.group(1).upper()
    sensor = minmax_match.group(2)
    value = minmax_match.group(3)
    rest = minmax_match.group(4)
    new_sensor = f"[{sensor}]" if " " in sensor else sensor
    return f"  {cmd} {new_sensor} {value}{rest}", f"{cmd} '{sensor}' '{value}' -> {cmd} {new_sensor} {value}"


def _migrate_save_line(stripped: str) -> tuple[str | None, str | None]:
    """Transform SAVE 'label' -> SAVE label. Returns (new_line, change) or (None, None)."""
    return _migrate_simple_quoted_line(stripped, "SAVE")


def _migrate_single_line(line: str) -> tuple[list[str], list[str]]:
    """Apply all line-level migrations to one source line. Returns (new_lines, changes)."""
    stripped = line.strip()
    new_lines, change = _migrate_goal_line(line, stripped)
    if new_lines is not None:
        return new_lines, ([change] if change else [])
    for migrator in (
        lambda: _migrate_loop_line(line, stripped),
        lambda: _migrate_endloop_line(stripped),
        lambda: _migrate_set_line(line, stripped),
        lambda: _migrate_wait_line(stripped),
        lambda: _migrate_minmax_line(stripped),
        lambda: _migrate_save_line(stripped),
    ):
        new_line, change = migrator()
        if new_line is not None:
            return [new_line], ([change] if change else [])
    return [line], []


def migrate_content(content: str, filename: str) -> tuple[str, list[str]]:
    """Zmigruj zawartość pliku do VERSION: 4.

    Returns:
        (new_content, changes_log)
    """
    new_lines, changes = _migrate_version_header(content)
    for line in content.split("\n"):
        migrated, line_changes = _migrate_single_line(line)
        new_lines.extend(migrated)
        changes.extend(line_changes)
    return canonicalize_oql_text("\n".join(new_lines)), changes


def _scan_files(files: list[Path]) -> tuple[list[Path], list[tuple[Path, str]], list[tuple[Path, str]]]:
    """Categorize .oql files into already_v4, needs_migration, and read errors."""
    already_v4: list[Path] = []
    needs_migration: list[tuple[Path, str]] = []
    errors: list[tuple[Path, str]] = []
    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8")
            version = extract_version(content)
            if version == OQL_VERSION_CURRENT:
                already_v4.append(filepath)
            elif version is not None:
                needs_migration.append((filepath, f"VERSION: {version}"))
            else:
                needs_migration.append((filepath, "brak VERSION"))
        except Exception as e:
            errors.append((filepath, str(e)))
    return already_v4, needs_migration, errors


def _perform_migration(needs_migration: list[tuple[Path, str]], root: Path) -> None:
    """Write migrated content for each file that needs it."""
    print("🚀 Rozpoczynam migrację...")
    migrated = 0
    for filepath, _ in needs_migration:
        try:
            content = filepath.read_text(encoding="utf-8")
            new_content, changes = migrate_content(content, str(filepath))
            if changes:
                filepath.write_text(new_content, encoding="utf-8")
                print(f"  ✓ {filepath.relative_to(root)}: {', '.join(changes[:3])}")
                migrated += 1
            else:
                print(f"  - {filepath.relative_to(root)}: brak zmian")
        except Exception as e:
            print(f"  ✗ {filepath.relative_to(root)}: BŁĄD - {e}")
    print(f"\n✅ Zmigrowano {migrated} plików")


def _perform_dry_run(needs_migration: list[tuple[Path, str]], root: Path) -> None:
    """Print a dry-run preview of migrations for the first three files."""
    print("🔍 Dry-run: pokazuję przykładowe zmiany...")
    for filepath, _ in needs_migration[:3]:
        content = filepath.read_text(encoding="utf-8")
        new_content, changes = migrate_content(content, str(filepath))
        print(f"\n  📄 {filepath.relative_to(root)}:")
        for ch in changes[:5]:
            print(f"     - {ch}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate .oql files to VERSION: 4")
    parser.add_argument("--root", default=".", help="Root directory to search")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files, just show what would change")
    parser.add_argument("--check-db", action="store_true", help="Check database via API")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    print(f"🔍 Szukam plików .oql w: {root}")
    files = find_oql_files(root)
    print(f"Znaleziono {len(files)} plików .oql\n")

    already_v4, needs_migration, errors = _scan_files(files)

    print(f"📊 RAPORT:")
    print(f"  ✅ Już w VERSION: 4: {len(already_v4)}")
    print(f"  ⚠️  Wymaga migracji: {len(needs_migration)}")
    print(f"  ❌ Błędy odczytu: {len(errors)}")
    print()

    if already_v4:
        print(f"✅ Pliki już w VERSION: 4 ({len(already_v4)}):")
        for f in already_v4[:10]:
            print(f"    {f.relative_to(root)}")
        if len(already_v4) > 10:
            print(f"    ... i {len(already_v4) - 10} więcej")
        print()

    if needs_migration:
        print(f"⚠️  Pliki wymagające migracji ({len(needs_migration)}):")
        for f, reason in needs_migration[:10]:
            print(f"    {f.relative_to(root)} ({reason})")
        if len(needs_migration) > 10:
            print(f"    ... i {len(needs_migration) - 10} więcej")
        print()
        if not args.dry_run:
            _perform_migration(needs_migration, root)
        else:
            _perform_dry_run(needs_migration, root)

    if errors:
        print(f"\n❌ Błędy ({len(errors)}):")
        for f, e in errors:
            print(f"    {f.relative_to(root)}: {e}")

    if args.check_db:
        print("\n" + "="*50)
        print("🔍 SPRAWDZANIE BAZY DANYCH (API)")
        print("="*50)
        check_database()

    return 0


def check_database():
    """Sprawdź scenariusze w bazie danych przez API."""
    import json
    import urllib.request
    
    try:
        # Spróbuj port 8202 (backend API)
        urls_to_try = [
            "http://localhost:8202/api/v1/scenarios",
            "http://localhost:8096/api/v1/scenarios",
            "http://localhost:8202/firmware/api/v1/scenarios",
        ]
        
        data = None
        for url in urls_to_try:
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = json.loads(resp.read().decode())
                    print(f"✅ Połączono z: {url}")
                    break
            except Exception as e:
                print(f"  ❌ {url}: {e}")
                continue
        
        if data is None:
            print("❌ Nie udało się połączyć z żadnym endpointem API")
            return
        
        print(f"\n📊 Znaleziono {len(data)} scenariuszy w bazie:")
        
        for scenario in data:
            sid = scenario.get("id", "NO_ID")
            name = scenario.get("name", "NO_NAME")
            code = scenario.get("code") or scenario.get("dsl")
            
            if code:
                # Sprawdź wersję w kodzie
                version_match = re.search(r"VERSION\s*:\s*(\d+)", code, re.IGNORECASE)
                if version_match:
                    version = int(version_match.group(1))
                    if version == OQL_VERSION_CURRENT:
                        print(f"  ✅ {sid}: VERSION: {version}")
                    else:
                        print(f"  ⚠️  {sid}: VERSION: {version} (oczekiwano: {OQL_VERSION_CURRENT})")
                else:
                    print(f"  ❌ {sid}: BRAK VERSION (code present but no version header)")
            else:
                print(f"  ℹ️  {sid}: {name} (brak kodu źródłowego - przechowywany jako struktura JSON)")
                
    except Exception as e:
        print(f"❌ Błąd podczas sprawdzania bazy: {e}")


if __name__ == "__main__":
    raise SystemExit(main())
