"""Resolve the application release version.

The helper prefers the version encoded in the current Git tag, then falls back
through repository VERSION files and package metadata. It is intentionally
side-effect free so backend, firmware, and deployment tooling can reuse it.
"""

from __future__ import annotations

from collections.abc import Iterable
from json import JSONDecodeError
import json
import os
import subprocess
from pathlib import Path


def clean_version(raw: str | None) -> str:
    """Normalize a raw version string to plain semver text."""

    if raw is None:
        return ""
    value = str(raw).strip()
    if not value:
        return ""
    if value.startswith(("v", "V")) and len(value) > 1 and value[1].isdigit():
        value = value[1:]
    return value


def _run_git(project_root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_root), *args],
            capture_output=True,
            check=False,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return None
    if completed.returncode != 0:
        return None
    output = completed.stdout.strip()
    return output or None


def _read_version_from_package_json(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, JSONDecodeError):
        return None
    if isinstance(data, dict):
        return clean_version(data.get("version")) or None
    return None


def _read_version_from_text(path: Path) -> str | None:
    try:
        if not path.exists():
            return None
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return clean_version(value) or None


def _version_candidates(project_root: Path) -> Iterable[Path]:
    yield project_root / "VERSION"
    yield project_root / "package.json"
    yield project_root / "frontend" / "package.json"
    yield project_root / "backend" / "VERSION"
    yield project_root / "firmware" / "VERSION"


def resolve_release_version(
    project_root: Path | None = None,
    *,
    env_var: str = "SERVICE_VERSION",
    default: str = "0.0.0",
) -> str:
    """Resolve the release version for the given project root.

    Priority order:
    1. Exact Git tag pointing at HEAD.
    2. Nearest Git tag (cleaned, if the repo has tags but HEAD is dirty).
    3. Explicit environment variable override.
    4. Repository VERSION / package.json fallbacks.
    5. ``default``.
    """

    root = Path(project_root) if project_root else Path(__file__).resolve().parents[1]

    for git_args in (
        ("tag", "--points-at", "HEAD", "--sort=-version:refname"),
        ("describe", "--tags", "--abbrev=0", "--match", "v*"),
    ):
        git_value = _run_git(root, *git_args)
        if git_value:
            for line in git_value.splitlines():
                cleaned = clean_version(line)
                if cleaned:
                    return cleaned

    for candidate in _version_candidates(root):
        value: str | None
        if candidate.suffix == ".json":
            value = _read_version_from_package_json(candidate)
        else:
            value = _read_version_from_text(candidate)
        if value:
            return value

    env_value = clean_version(os.getenv(env_var))
    if env_value:
        return env_value

    return clean_version(default) or "0.0.0"


def main() -> None:
    print(resolve_release_version())


if __name__ == "__main__":
    main()
