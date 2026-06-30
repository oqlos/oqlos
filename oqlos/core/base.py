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

import yaml

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
    """Hierarchical key-value store with interpolation support."""

    def __init__(self, initial: dict[str, Any] | None = None, parent: VariableStore | None = None):
        self._vars: dict[str, Any] = dict(initial or {})
        self.parent = parent

    def set(self, key: str, value: Any, local: bool = True) -> None:
        """Set variable value. If local=False, try to update in parent if exists."""
        if not local and self.parent and self.parent.has(key):
            self.parent.set(key, value, local=False)
        else:
            self._vars[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get variable value, searching up the hierarchy."""
        if key in self._vars:
            return self._vars[key]
        if self.parent:
            return self.parent.get(key, default)
        return default

    def has(self, key: str) -> bool:
        """Check if variable exists in this or parent stores."""
        return key in self._vars or (self.parent.has(key) if self.parent else False)

    def all(self, include_parents: bool = True) -> dict[str, Any]:
        """Get all variables visible from this store."""
        if not self.parent or not include_parents:
            return dict(self._vars)
        merged = self.parent.all(include_parents=True)
        merged.update(self._vars)
        return merged

    def clear(self) -> None:
        self._vars.clear()

    def interpolate(self, text: str) -> str:
        """Replace ${var} and $var references in text using hierarchical lookup."""
        def _repl(m: re.Match) -> str:
            key = m.group(1) or m.group(2)
            val = self.get(key)
            return str(val) if val is not None else m.group(0)
        # ${var} first, then $var (word chars only)
        text = re.sub(r'\$\{([^}]+)\}', _repl, text)
        text = re.sub(r'\$([A-Za-z_]\w*)', _repl, text)
        return text

# ── Output / logging ────────────────────────────────────────────────────────

class InterpreterOutput:
    """Collects interpreter output lines for display or testing, and optionally broadcasts events."""

    def __init__(self, quiet: bool = False, bridge: EventBridge | None = None, yaml_output: bool = False):
        self.quiet = quiet
        self.bridge = bridge
        self.yaml_output = yaml_output
        self.lines: list[str] = []
        self.yaml_data: dict[str, Any] = {}

    def emit(self, msg: str, event_type: str = "log") -> None:
        self.lines.append(msg)
        if not self.quiet:
            if self.yaml_output:
                # For YAML output, we'll collect structured data instead
                pass
            else:
                print(msg)
        
        if self.bridge and self.bridge.connected:
            # We use a helper because send_event is async.
            # In a synchronous interpreter, we might need a background thread 
            # or use asyncio.run if not already in an event loop.
            # For simplicity in Sprint 4, we'll try to use a fire-and-forget 
            # or check if we are already in an async context.
            self._broadcast_event(event_type, {"message": msg})

    def _broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self.bridge:
            return
        try:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.create_task(self.bridge.send_event(event_type, payload))
            else:
                asyncio.run(self.bridge.send_event(event_type, payload))
        except Exception:
            pass

    def _emit_status(self, msg: str, *, yaml_key: str, prefix: str, event_type: str) -> None:
        if self.yaml_output:
            self.yaml_data.setdefault(yaml_key, []).append(msg)
        else:
            self.emit(f"{prefix}{msg}", event_type)

    def info(self, msg: str) -> None:
        self._emit_status(msg, yaml_key="info", prefix="ℹ️  ", event_type="info")

    def ok(self, msg: str) -> None:
        self._emit_status(msg, yaml_key="success", prefix="✅ ", event_type="success")

    def fail(self, msg: str) -> None:
        self._emit_status(msg, yaml_key="failure", prefix="❌ ", event_type="failure")

    def warn(self, msg: str) -> None:
        self._emit_status(msg, yaml_key="warning", prefix="⚠️  ", event_type="warning")

    def error(self, msg: str) -> None:
        self._emit_status(msg, yaml_key="error", prefix="❌ ", event_type="error")

    def step(self, icon: str, msg: str) -> None:
        if self.yaml_output:
            self.yaml_data.setdefault("steps", []).append({"icon": icon, "message": msg})
        else:
            self.emit(f"{icon} {msg}", "step")

    def output_yaml(self) -> None:
        """Output collected YAML data to stdout."""
        if self.yaml_output and self.yaml_data and not self.quiet:
            print(yaml.dump(self.yaml_data, default_flow_style=False, sort_keys=False), end="")

# ── Base interpreter ─────────────────────────────────────────────────────────

class BaseInterpreter(ABC):
    """Abstract base for language interpreters."""

    def __init__(self, variables: dict[str, Any] | None = None, quiet: bool = False, bridge_url: str | None = None, yaml_output: bool = False):
        self.bridge = EventBridge(bridge_url) if bridge_url else None
        self.vars = VariableStore(variables)
        self.out = InterpreterOutput(quiet=quiet, bridge=self.bridge, yaml_output=yaml_output)
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
        """Parse + execute in one step with EventBridge support."""
        import asyncio
        t0 = time.monotonic()
        
        # Connect bridge if available
        if self.bridge:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we are already in a loop, we can't block here properly without await.
                    # This is a limitation of this shim.
                    pass
                else:
                    loop.run_until_complete(self.bridge.connect())
            except Exception:
                pass

        parsed = self.parse(source, filename)
        result = self.execute(parsed)
        result.duration_ms = (time.monotonic() - t0) * 1000
        
        # Disconnect bridge
        if self.bridge:
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    loop.run_until_complete(self.bridge.disconnect())
            except Exception:
                pass
                
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
