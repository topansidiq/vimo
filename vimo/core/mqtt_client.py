"""
MQTT client wrapper for background ingestion.
"""

import json
import threading
from typing import Any, Callable, Iterable, Optional, Set

import paho.mqtt.client as mqtt


class MQTTClient:
    """Thin wrapper around paho-mqtt with dynamic subscriptions."""

    def __init__(
        self,
        host: str,
        port: int,
        on_data: Callable[[str, dict], None],
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        auto_reconnect: bool = True,
    ):
        self._host = host
        self._port = int(port)
        self._on_data = on_data
        self._on_connect_cb = on_connect
        self._on_disconnect_cb = on_disconnect
        self._auto_reconnect = auto_reconnect

        self._lock = threading.Lock()
        self._topics: Set[str] = set()
        self._connected = False
        self._running = False

        self._client = mqtt.Client()
        self._client.on_connect = self._handle_connect
        self._client.on_disconnect = self._handle_disconnect
        self._client.on_message = self._handle_message
        if self._auto_reconnect:
            self._client.reconnect_delay_set(min_delay=2, max_delay=15)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._client.connect_async(self._host, self._port, keepalive=30)
        self._client.loop_start()

    def stop(self) -> None:
        self._running = False
        try:
            self._client.disconnect()
        except Exception:
            pass
        self._client.loop_stop()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def set_topics(self, topics: Iterable[str]) -> None:
        clean_topics = {str(topic).strip() for topic in topics if str(topic).strip()}
        with self._lock:
            remove_topics = self._topics - clean_topics
            add_topics = clean_topics - self._topics
            self._topics = clean_topics

        if not self._connected:
            return

        for topic in remove_topics:
            try:
                self._client.unsubscribe(topic)
            except Exception:
                pass

        for topic in add_topics:
            try:
                self._client.subscribe(topic, qos=0)
            except Exception:
                pass

    def _handle_connect(self, _client, _userdata, _flags, rc, _properties=None):
        self._connected = int(rc) == 0
        if not self._connected:
            return

        with self._lock:
            topics = list(self._topics)

        for topic in topics:
            try:
                self._client.subscribe(topic, qos=0)
            except Exception:
                pass

        if self._on_connect_cb:
            self._on_connect_cb()

    def _handle_disconnect(self, _client, _userdata, _flags_or_rc=None, _properties=None):
        was_connected = self._connected
        self._connected = False
        if was_connected and self._on_disconnect_cb:
            self._on_disconnect_cb()

    def _handle_message(self, _client, _userdata, msg):
        try:
            text = msg.payload.decode("utf-8", errors="ignore").strip()
            if not text:
                return
            payload: Any = json.loads(text)
            if not isinstance(payload, dict):
                return
            self._on_data(msg.topic, payload)
        except Exception:
            # Keep MQTT loop alive for malformed payloads.
            pass
