"""
dsl/interpreter/base.py — Shared base classes for CQL and IQL interpreters.
"""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ── Result types ─────────────────────────────────────────────────────────────

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    WARNING = "warning"

@dataclass
class StepResult:
    name: str
    status: StepStatus
    value: Any = None
    message: str = ""
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

@dataclass
class ScriptResult:
    source: str
    ok: bool
    steps: list[StepResult] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def passed(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for s in self.steps if s.status in (StepStatus.FAILED, StepStatus.ERROR))

    def summary(self) -> str:
        total = len(self.steps)
        icon = "✅" if self.ok else "❌"
        return f"{icon} {self.source}: {self.passed}/{total} passed, {self.failed} failed ({self.duration_ms:.0f}ms)"

# ── Variable store ───────────────────────────────────────────────────────────

class VariableStore:
    """Simple key-value store with interpolation support."""

    def __init__(self, initial: dict[str, Any] | None = None):
        self._vars: dict[str, Any] = dict(initial or {})

    def set(self, key: str, value: Any) -> None:
        self._vars[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._vars.get(key, default)

    def has(self, key: str) -> bool:
        return key in self._vars

    def all(self) -> dict[str, Any]:
        return dict(self._vars)

    def clear(self) -> None:
        self._vars.clear()

    def interpolate(self, text: str) -> str:
        """Replace ${var} and $var references in text."""
        def _repl(m: re.Match) -> str:
            key = m.group(1) or m.group(2)
            val = self._vars.get(key)
            return str(val) if val is not None else m.group(0)
        # ${var} first, then $var (word chars only)
        text = re.sub(r'\$\{([^}]+)\}', _repl, text)
        text = re.sub(r'\$([A-Za-z_]\w*)', _repl, text)
        return text

# ── Output / logging ────────────────────────────────────────────────────────

class InterpreterOutput:
    """Collects interpreter output lines for display or testing."""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self.lines: list[str] = []

    def emit(self, msg: str) -> None:
        self.lines.append(msg)
        if not self.quiet:
            print(msg)

    def info(self, msg: str) -> None:
        self.emit(f"ℹ️  {msg}")

    def ok(self, msg: str) -> None:
        self.emit(f"✅ {msg}")

    def fail(self, msg: str) -> None:
        self.emit(f"❌ {msg}")

    def warn(self, msg: str) -> None:
        self.emit(f"⚠️  {msg}")

    def error(self, msg: str) -> None:
        self.emit(f"❌ {msg}")

    def step(self, icon: str, msg: str) -> None:
        self.emit(f"{icon} {msg}")

# ── Base interpreter ─────────────────────────────────────────────────────────

class BaseInterpreter(ABC):
    """Abstract base for language interpreters."""

    def __init__(self, variables: dict[str, Any] | None = None, quiet: bool = False):
        self.vars = VariableStore(variables)
        self.out = InterpreterOutput(quiet=quiet)
        self.results: list[StepResult] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @abstractmethod
    def parse(self, source: str, filename: str = "<string>") -> Any:
        """Parse source into an AST / structure."""
        ...

    @abstractmethod
    def execute(self, parsed: Any) -> ScriptResult:
        """Execute parsed structure."""
        ...

    def run(self, source: str, filename: str = "<string>") -> ScriptResult:
        """Parse + execute in one step."""
        t0 = time.monotonic()
        parsed = self.parse(source, filename)
        result = self.execute(parsed)
        result.duration_ms = (time.monotonic() - t0) * 1000
        return result

    def run_file(self, path: str) -> ScriptResult:
        """Load file and run."""
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        return self.run(source, filename=path)

    # Helpers
    @staticmethod
    def strip_comments(lines: list[str]) -> list[str]:
        """Remove comment-only lines and inline comments."""
        out = []
        for line in lines:
            stripped = line.split("#")[0].rstrip() if "#" in line else line.rstrip()
            out.append(stripped)
        return out

# ── WebSocket bridge (optional, for browser sync) ───────────────────────────

class EventBridge:
    """Optional WebSocket bridge to DSL Event Server (port 8104).

    When connected, events emitted by interpreters are broadcast
    to all connected browser clients via the event server.
    """

    def __init__(self, url: str = "ws://localhost:8104/cli"):
        self.url = url
        self._ws: Any = None
        self._connected = False

    async def connect(self) -> bool:
        try:
            import websockets
            self._ws = await websockets.connect(self.url)
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    async def disconnect(self) -> None:
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
            self._connected = False

    async def send_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self._connected or not self._ws:
            return
        import json
        event = {
            "id": f"evt-{int(time.time() * 1000):x}-{id(payload) & 0xffff:04x}",
            "type": event_type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": payload,
            "metadata": {"source": "cli"},
        }
        try:
            await self._ws.send(json.dumps(event))
        except Exception:
            self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected
