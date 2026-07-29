#!/usr/bin/env python3
"""Generate a reproducible static inventory for the OqlOS refactor roadmap."""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any


ROUTE_METHODS = {"delete", "get", "head", "options", "patch", "post", "put"}
SOURCE_SUFFIXES = {".js", ".jsx", ".py", ".ts", ".tsx"}
EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "project",
    "venv",
}
SETTINGS_FILENAMES = {
    ".env",
    "_runtime_settings.py",
    "config.py",
    "environment.py",
    "runtime_env.py",
    "settings.py",
}
RAW_EXCEPTION_NAMES = {"HTTPException", "RuntimeError", "ValueError"}
JS_ENV_PATTERN = re.compile(r"(?:import\.meta\.env|process\.env)(?:\.|\[)")


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_excluded(path: Path, root: Path) -> bool:
    relative = path.resolve().relative_to(root.resolve())
    return any(part in EXCLUDED_DIRS for part in relative.parts)


def _is_test_file(path: Path, root: Path) -> bool:
    relative = path.resolve().relative_to(root.resolve())
    return "tests" in relative.parts or path.name.endswith((".test.js", ".test.ts", "_test.py")) or path.name.startswith("test_")


def _source_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in SOURCE_SUFFIXES
        and not _is_excluded(path, root)
        and not _is_test_file(path, root)
    )


def _annotation(node: ast.expr | None) -> str | None:
    return ast.unparse(node) if node is not None else None


def _route_decorator(node: ast.expr) -> dict[str, Any] | None:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    method = node.func.attr.lower()
    if method not in ROUTE_METHODS:
        return None
    route_path: str | None = None
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        route_path = node.args[0].value
    keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
    if route_path is None:
        path_node = keywords.get("path")
        if isinstance(path_node, ast.Constant) and isinstance(path_node.value, str):
            route_path = path_node.value
    if route_path is None:
        return None
    return {
        "method": method.upper(),
        "route_path": route_path,
        "response_model": _annotation(keywords.get("response_model")),
        "status_code": _annotation(keywords.get("status_code")),
    }


def _call_name(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _contains_false_success_dict(function: ast.AST) -> bool:
    for node in ast.walk(function):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and key.value in {"ok", "success"}
                and isinstance(value, ast.Constant)
                and value.value is False
            ):
                return True
    return False


def _uses_os_environment(node: ast.AST) -> bool:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            return node.func.value.id == "os" and node.func.attr == "getenv"
        if isinstance(node.func.value, ast.Attribute):
            return (
                isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "os"
                and node.func.value.attr == "environ"
                and node.func.attr == "get"
            )
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "os"
        and node.value.attr == "environ"
    )


def _location(path: Path, root: Path, line: int, **extra: Any) -> dict[str, Any]:
    return {"file": _relative(path, root), "line": line, **extra}


def _audit_python(path: Path, root: Path, report: dict[str, Any]) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        report["parse_failures"].append(
            _location(path, root, getattr(exc, "lineno", 0) or 0, error=str(exc))
        )
        return

    settings_file = path.name in SETTINGS_FILENAMES
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = [
                route
                for decorator in node.decorator_list
                if (route := _route_decorator(decorator)) is not None
            ]
            for route in decorators:
                annotation = _annotation(node.returns)
                entry = _location(
                    path,
                    root,
                    node.lineno,
                    function=node.name,
                    return_annotation=annotation,
                    **route,
                )
                report["public_routes"].append(entry)
                normalized = (annotation or "").replace(" ", "")
                if "dict[str,Any]" in normalized or "Dict[str,Any]" in normalized:
                    report["routes_returning_dict_any"].append(entry)
                if route["response_model"] is None and (
                    annotation is None
                    or annotation in {"Any", "dict", "Dict"}
                    or "dict[" in normalized
                    or "Dict[" in normalized
                ):
                    report["routes_with_generic_response"].append(entry)
                if _contains_false_success_dict(node) and route["status_code"] in {
                    None,
                    "200",
                    "status.HTTP_200_OK",
                }:
                    report["routes_with_false_success_at_http_200"].append(entry)
        elif isinstance(node, ast.Raise):
            exception_name = _call_name(node.exc.func if isinstance(node.exc, ast.Call) else node.exc)
            if exception_name in RAW_EXCEPTION_NAMES:
                report["raw_exceptions"].append(
                    _location(path, root, node.lineno, exception=exception_name)
                )
        elif isinstance(node, ast.ExceptHandler):
            exception_name = _call_name(node.type)
            if node.type is None or exception_name in {"BaseException", "Exception"}:
                report["broad_exception_handlers"].append(
                    _location(path, root, node.lineno, exception=exception_name or "bare")
                )
        if not settings_file and _uses_os_environment(node):
            report["environment_reads_outside_settings"].append(
                _location(path, root, getattr(node, "lineno", 0))
            )


def _audit_javascript_environment(path: Path, root: Path, report: dict[str, Any]) -> None:
    if path.name in SETTINGS_FILENAMES or "config" in path.stem.lower() or "env" in path.stem.lower():
        return
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    for line_number, line in enumerate(content.splitlines(), 1):
        if JS_ENV_PATTERN.search(line):
            report["environment_reads_outside_settings"].append(
                _location(path, root, line_number)
            )


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _tool_version(command: str) -> dict[str, str | None]:
    executable = shutil.which(command)
    if executable is None:
        return {"executable": None, "version": None}
    result = subprocess.run(
        [executable, "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = (result.stdout or result.stderr).strip()
    return {"executable": executable, "version": output or None}


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_report(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    source_files = _source_files(root)
    git_status = _git(root, "status", "--porcelain").splitlines()
    generated_paths: set[str] = set()
    for artifact in (output, output.parent / "analysis.toon.yaml", output.parent / "map.toon.yaml"):
        try:
            generated_paths.add(artifact.resolve().relative_to(root).as_posix())
        except ValueError:
            pass
    non_generated_changes = [
        line
        for line in git_status
        if not any(line[3:].endswith(path) for path in generated_paths)
    ]
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "root": str(root),
        "git_commit": _git(root, "rev-parse", "HEAD"),
        "git_dirty": bool(non_generated_changes),
        "git_dirty_including_generated_artifacts": bool(git_status),
        "git_status_excluding_generated_artifacts": non_generated_changes,
        "generator": {
            "audit_command": f"python scripts/refactor_audit.py --root {root} --output {output}",
            "code2llm_command": "code2llm . -m hybrid -f toon,map --strategy standard --toon-yaml --no-png --no-cache --no-chunk -o <temp>",
            "code2llm": _tool_version("code2llm"),
        },
        "artifacts": {
            "analysis.toon.yaml": _sha256(output.parent / "analysis.toon.yaml"),
            "map.toon.yaml": _sha256(output.parent / "map.toon.yaml"),
        },
        "source_file_count": len(source_files),
        "public_routes": [],
        "routes_returning_dict_any": [],
        "routes_with_generic_response": [],
        "routes_with_false_success_at_http_200": [],
        "environment_reads_outside_settings": [],
        "raw_exceptions": [],
        "broad_exception_handlers": [],
        "large_modules": [],
        "parse_failures": [],
    }

    for path in source_files:
        line_count = len(path.read_bytes().splitlines())
        if line_count >= 400:
            report["large_modules"].append(
                {"file": _relative(path, root), "lines": line_count}
            )
        if path.suffix == ".py":
            _audit_python(path, root, report)
        else:
            _audit_javascript_environment(path, root, report)

    report["large_modules"].sort(key=lambda item: (-item["lines"], item["file"]))
    report["summary"] = {
        key: len(value)
        for key, value in report.items()
        if isinstance(value, list)
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    report = generate_report(args.root, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
