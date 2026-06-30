"""Map legacy connect-data scenario ids/filenames to canonical ``scenarios/`` files."""

from __future__ import annotations

from pathlib import Path

# ids / export filenames from 2026-04-30 DB snapshot → canonical repo files
LEGACY_SCENARIO_ALIASES: dict[str, str] = {
    "ts-flow": "test-przeplywu.oql",
    "ts-kalibracja-czujnikow": "kalibracja-czujnikow.oql",
    "ts-kaskadowy-cisnienie": "kaskadowy-pomiar-cisnienia-z-przelaczaniem-czujnikow.oql",
    "ts-pelny-test-cisnieniowy": "pelny-test-cisnieniowy-z-przelaczaniem-zakresow.oql",
    "ts-spadek-cisnienia": "test-spadku-cisnienia-automatu.oql",
    "ts-wytrzymalosc-mech": "test-wytrzymalosci-mechanicznej.oql",
    "ts-szczelnosc-maski": "test-szczelnosci-maski.oql",
    "ts-temp-wilgotnosc": "test-temperatury-i-wilgotnosci.oql",
}


def resolve_canonical_scenario_file(scenario_id: str, scenarios_dir: Path) -> Path | None:
    """Return canonical ``.oql`` path for a scenario id or basename."""
    key = scenario_id.strip()
    if key.endswith(".oql"):
        key = key[:-4]
    candidates = [key + ".oql"]
    alias = LEGACY_SCENARIO_ALIASES.get(key)
    if alias:
        candidates.insert(0, alias)
    for name in candidates:
        path = scenarios_dir / name
        if path.is_file():
            return path
    return None
