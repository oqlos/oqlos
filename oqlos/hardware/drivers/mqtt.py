"""
oqlos.hardware.drivers.mqtt — MQTT protocol driver for OqlOS HAL.
"""

from __future__ import annotations

import json
import logging
import asyncio
from typing import Any

import paho.mqtt.client as mqtt

from oqlos.hardware.protocol import HardwareProtocol, ProtocolType
from oqlos.hardware.registry import DriverRegistry


@DriverRegistry.register(ProtocolType.MQTT)
class MqttDriver(HardwareProtocol):
    """
    MQTT driver for the Hardware Abstraction Layer.
    Mapped to ProtocolType.MQTT.
    """
    protocol_type = ProtocolType.MQTT

    def __init__(self):
        self.client = mqtt.Client()
        self.broker_url = ""
        self.broker_port = 1883
        self.last_messages: dict[str, Any] = {}
        self._connected = False
        self._loop_task: asyncio.Task | None = None

    async def connect(self, config: dict[str, Any]) -> bool:
        """Connect to the MQTT broker."""
        self.broker_url = config.get("host", "localhost")
        self.broker_port = config.get("port", 1883)
        username = config.get("username")
        password = config.get("password")

        if username:
            self.client.username_pw_set(username, password)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        try:
            self.client.connect(self.broker_url, self.broker_port, 60)
            self.client.loop_start()
            self._connected = True
            logging.info(f"MQTT Connected to {self.broker_url}:{self.broker_port}")
            return True
        except Exception as e:
            logging.error(f"MQTT Connection failed: {e}")
            self._connected = False
            return False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("Connected successfully to MQTT Broker")
        else:
            logging.error(f"MQTT Connect failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            payload = msg.payload.decode()
        
        self.last_messages[topic] = payload
        logging.debug(f"MQTT Received: {topic} -> {payload}")

    async def read(self, address: str, **kwargs: Any) -> Any:
        """
        Read the last message from a topic. 
        Note: subscribe to the topic happens if not already present.
        """
        topic = address
        if topic not in self.last_messages:
            self.client.subscribe(topic)
            # Wait a bit for message to arrive if needed or just return None
            await asyncio.sleep(0.1)
        
        return self.last_messages.get(topic)

    async def write(self, address: str, value: Any, **kwargs: Any) -> bool:
        """Publish a message to an MQTT topic."""
        topic = address
        if isinstance(value, (dict, list)):
            payload = json.dumps(value)
        else:
            payload = str(value)
        
        try:
            info = self.client.publish(topic, payload)
            info.wait_for_publish()
            return True
        except Exception as e:
            logging.error(f"MQTT Publish failed: {e}")
            return False

    async def discover(self) -> list[dict[str, Any]]:
        """Non-trivial for MQTT unless using some standard like Homie or Home Assistant Discovery."""
        return []

    async def health_check(self) -> dict[str, Any]:
        """Check if connected to broker."""
        return {
            "status": "ok" if self._connected and self.client.is_connected() else "failed",
            "broker": f"{self.broker_url}:{self.broker_port}",
            "connected": self.client.is_connected()
        }

    async def disconnect(self) -> None:
        """Disconnect and stop loop."""
        self.client.loop_stop()
        self.client.disconnect()
        self._connected = False
