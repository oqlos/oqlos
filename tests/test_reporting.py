import asyncio
import os
import sys
from typing import Any

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from oqlos.core.base import EventBridge, InterpreterOutput

class MockWS:
    async def send(self, msg):
        pass
    async def close(self):
        pass

class MockBridge(EventBridge):
    def __init__(self):
        super().__init__("ws://mock")
        self.sent_events = []
        self._connected = True
        self._ws = MockWS()

    async def send_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self.sent_events.append({"type": event_type, "payload": payload})

def test_reporting():
    print("Testing Real-time Reporting via MockBridge...")
    bridge = MockBridge()
    out = InterpreterOutput(quiet=True, bridge=bridge)
    
    out.step("🔍", "Test Step")
    out.ok("All good")
    out.error("Oops")
    
    # Check sent events
    expected_types = ["step", "success", "error"]
    sent_types = [e["type"] for e in bridge.sent_events]
    
    print(f"Sent event types: {sent_types}")
    assert sent_types == expected_types, f"Mismatch: {sent_types}"
    print("✅ Real-time reporting verified via MockBridge!")

if __name__ == "__main__":
    test_reporting()
