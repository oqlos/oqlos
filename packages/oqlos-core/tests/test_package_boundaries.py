from __future__ import annotations

import ast
from pathlib import Path


CORE_ROOT = Path(__file__).parents[1] / "src" / "oqlos" / "core"


def test_core_package_does_not_import_fastapi() -> None:
    violations: list[str] = []
    for path in CORE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            if any(module == "fastapi" or module.startswith("fastapi.") for module in modules):
                violations.append(f"{path.relative_to(CORE_ROOT)}:{node.lineno}")

    assert violations == [], f"FastAPI imports cross the oqlos-core boundary: {violations}"
