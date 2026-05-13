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
from oqlos.tools.cql_cli.formatting import canonicalize_oql_text


def _quote_oql(value: str) -> str:
    return "'" + str(value or "").strip().replace("\\", "\\\\").replace("'", "\\'") + "'"


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


def migrate_content(content: str, filename: str) -> tuple[str, list[str]]:
    """Zmigruj zawartość pliku do VERSION: 4.
    
    Returns:
        (new_content, changes_log)
    """
    changes = []
    lines = content.split("\n")
    new_lines = []
    
    # 1. Dodaj VERSION: 4 jeśli brak
    if not has_version_header(content):
        new_lines.append(f"VERSION: {OQL_VERSION_CURRENT}")
        changes.append("Dodano VERSION: 4 na początku")
    
    # 2. Przetwórz linie
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # GOAL: Name -> GOAL:\n  SET NAME 'Name'
        goal_match = re.match(r"^(GOAL)\s*:\s*(.+?)\s*$", stripped, re.IGNORECASE)
        if goal_match:
            goal_name = goal_match.group(2).strip()
            # Usuń cudzysłowy jeśli są
            if (goal_name.startswith('"') and goal_name.endswith('"')) or \
               (goal_name.startswith("'") and goal_name.endswith("'")):
                goal_name = goal_name[1:-1]
            
            new_lines.append("GOAL:")
            
            new_lines.append(f"  SET NAME {_quote_oql(goal_name)}")
            
            changes.append(f"GOAL: {goal_match.group(2)} -> GOAL: + SET NAME")
            i += 1
            continue
        
        # 3. Zamiana LOOP na REPEAT (jeśli jest w starej formie)
        if re.match(r"^LOOP\b", stripped, re.IGNORECASE):
            # Pobierz następną linię żeby zobaczyć kontekst
            loop_match = re.match(r"^LOOP\s+(\d+)\s+TIMES\s*$", stripped, re.IGNORECASE)
            if loop_match:
                count = loop_match.group(1)
                new_lines.append(f"REPEAT {count}:")
                changes.append(f"LOOP {count} TIMES -> REPEAT {count}:")
            else:
                new_lines.append(line)
            i += 1
            continue
        
        # 4. Zamiana ENDLOOP na REPEAT STOP
        if re.match(r"^ENDLOOP\s*$", stripped, re.IGNORECASE):
            new_lines.append("REPEAT STOP")
            changes.append("ENDLOOP -> REPEAT STOP")
            i += 1
            continue
        
        # 5. Zachowaj kanoniczne SET 'x' 'y'; pozostałe SET-y normalizuje post-process
        set_match = re.match(r"^SET\s+['\"]([^'\"]+)['\"]\s+['\"]([^'\"]+)['\"](.*)$", stripped, re.IGNORECASE)
        if set_match:
            new_lines.append(f"  SET {_quote_oql(set_match.group(1))} {_quote_oql(set_match.group(2))}{set_match.group(3)}")
            i += 1
            continue
        
        # 6. Zamiana WAIT 'X' na WAIT X
        wait_match = re.match(r"^WAIT\s+['\"](.+?)['\"]\s*$", stripped, re.IGNORECASE)
        if wait_match:
            duration = wait_match.group(1)
            new_lines.append(f"  WAIT {duration}")
            changes.append(f"WAIT '{duration}' -> WAIT {duration}")
            i += 1
            continue
        
        # 7. Zamiana MIN/MAX 'sensor' 'value' na MIN sensor value
        minmax_match = re.match(r"^(MIN|MAX)\s+['\"]([^'\"]+)['\"]\s+['\"]([^'\"]+)['\"](.*)$", stripped, re.IGNORECASE)
        if minmax_match:
            cmd = minmax_match.group(1).upper()
            sensor = minmax_match.group(2)
            value = minmax_match.group(3)
            rest = minmax_match.group(4)
            
            if " " in sensor:
                new_sensor = f"[{sensor}]"
            else:
                new_sensor = sensor
            
            new_lines.append(f"  {cmd} {new_sensor} {value}{rest}")
            changes.append(f"{cmd} '{sensor}' '{value}' -> {cmd} {new_sensor} {value}")
            i += 1
            continue
        
        # 8. Zamiana SAVE 'label' na SAVE label
        save_match = re.match(r"^SAVE\s+['\"]([^'\"]+)['\"]\s*$", stripped, re.IGNORECASE)
        if save_match:
            label = save_match.group(1)
            new_lines.append(f"  SAVE {label}")
            changes.append(f"SAVE '{label}' -> SAVE {label}")
            i += 1
            continue
        
        # Domyślnie: kopiuj linię
        new_lines.append(line)
        i += 1
    
    return canonicalize_oql_text("\n".join(new_lines)), changes


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
    
    # Statystyki
    already_v4 = []
    needs_migration = []
    errors = []
    
    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8")
            version = extract_version(content)
            
            if version == OQL_VERSION_CURRENT:
                already_v4.append(filepath)
            elif version is not None and version != OQL_VERSION_CURRENT:
                # Inna wersja niż 4
                needs_migration.append((filepath, f"VERSION: {version}"))
            else:
                # Brak wersji
                needs_migration.append((filepath, "brak VERSION"))
                
        except Exception as e:
            errors.append((filepath, str(e)))
    
    # Raport
    print(f"📊 RAPORT:")
    print(f"  ✅ Już w VERSION: 4: {len(already_v4)}")
    print(f"  ⚠️  Wymaga migracji: {len(needs_migration)}")
    print(f"  ❌ Błędy odczytu: {len(errors)}")
    print()
    
    if already_v4:
        print(f"✅ Pliki już w VERSION: 4 ({len(already_v4)}):")
        for f in already_v4[:10]:  # Pokaż max 10
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
        
        # Migracja
        if not args.dry_run:
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
        else:
            print("🔍 Dry-run: pokazuję przykładowe zmiany...")
            for filepath, _ in needs_migration[:3]:
                content = filepath.read_text(encoding="utf-8")
                new_content, changes = migrate_content(content, str(filepath))
                print(f"\n  📄 {filepath.relative_to(root)}:")
                for ch in changes[:5]:
                    print(f"     - {ch}")
    
    if errors:
        print(f"\n❌ Błędy ({len(errors)}):")
        for f, e in errors:
            print(f"    {f.relative_to(root)}: {e}")
    
    # Sprawdź bazę danych jeśli requested
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
