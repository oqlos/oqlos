"""
oqlos.shared.file_ops — Safe file operations within a sandboxed base directory.

Provides path-traversal-safe helpers used by the editor API and any other
component that needs to read/write files relative to a trusted directory.
"""

from __future__ import annotations

import pathlib
from typing import Iterator


class PathEscapeError(PermissionError):
    """Raised when a resolved path would escape the base directory."""


def _ensure_safe_path(base: pathlib.Path, rel: str) -> pathlib.Path:
    """Resolve *rel* relative to *base*, raising if the result escapes *base*.

    Args:
        base: Trusted root directory (must be absolute or resolvable).
        rel:  Relative path supplied by the caller (may contain '..').

    Returns:
        Resolved absolute path that is guaranteed to be inside *base*.

    Raises:
        PathEscapeError: If the resolved path is outside *base*.
    """
    base_resolved = base.resolve()
    full_path = (base_resolved / rel).resolve()
    if not str(full_path).startswith(str(base_resolved)):
        raise PathEscapeError(
            f"Access denied: '{rel}' resolves outside base directory '{base_resolved}'"
        )
    return full_path


def list_files(
    base: pathlib.Path,
    pattern: str = "*",
    recursive: bool = False,
) -> list[str]:
    """List files (not directories) matching *pattern* under *base*.

    Args:
        base:      Root directory to search.
        pattern:   Glob pattern (default ``"*"`` — all files).
        recursive: When True use ``rglob`` instead of ``glob``.

    Returns:
        Sorted list of path strings relative to *base*.
    """
    glob_fn = base.rglob if recursive else base.glob
    return sorted(
        str(p.relative_to(base))
        for p in glob_fn(pattern)
        if p.is_file()
    )


def iter_entries(base: pathlib.Path) -> Iterator[dict]:
    """Iterate over direct children of *base*, yielding info dicts.

    Each dict contains: ``name``, ``path`` (relative), ``size``, ``is_directory``.
    """
    for item in base.iterdir():
        rel = item.relative_to(base)
        yield {
            "name": item.name,
            "path": str(rel),
            "size": item.stat().st_size if item.is_file() else 0,
            "is_directory": item.is_dir(),
        }


def read_file(base: pathlib.Path, rel: str) -> str:
    """Read a file safely within *base*.

    Raises:
        PathEscapeError: Path escapes base directory.
        FileNotFoundError: File does not exist.
        IsADirectoryError: Path points to a directory.
    """
    full_path = _ensure_safe_path(base, rel)
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {rel}")
    if full_path.is_dir():
        raise IsADirectoryError(f"Path is a directory: {rel}")
    return full_path.read_text(encoding="utf-8")


def write_file(base: pathlib.Path, rel: str, content: str) -> pathlib.Path:
    """Write *content* to a file safely within *base*.

    Creates parent directories as needed.

    Returns:
        Resolved absolute path of the written file.

    Raises:
        PathEscapeError: Path escapes base directory.
    """
    full_path = _ensure_safe_path(base, rel)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return full_path
