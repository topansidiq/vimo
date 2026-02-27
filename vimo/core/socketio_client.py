"""
SocketIO Client — background thread that connects to the Flask-SocketIO bridge server.

Your bridge server (Flask + flask-socketio) subscribes to MQTT and re-emits sensor
data via SocketIO like this:

    socketio.emit("mpu_data", {
        "accelX": ..., "accelY": ..., "accelZ": ...,
        "gyroX": ...,  "gyroY": ...,  "gyroZ": ...,
        # Optional: machine_id to route to different machines
        "machine_id": "MACHINE-001"
    })

MACHINE ROUTING (priority order):
  1. JSON field named by machine_id_field setting (e.g. "machine_id")
  2. Falls back to default_machine_id from settings

NOTE — if you have multiple ESPs on different MQTT topics
(e.g. machine/vibration/1, machine/vibration/2), inject machine_id
in your bridge server's on_message callback like this:

    def on_message(client, userdata, msg):
        data = json.loads(msg.payload.decode())
        parts = msg.topic.split("/")
        idx = parts[-1] if parts[-1].isdigit() else "1"
        data["machine_id"] = f"MACHINE-{int(idx):03d}"
        socketio.emit("mpu_data", data)
"""

import threading
import time
import logging
import socketio as sio_lib
from typing import Callable, Optional

LOGGER = logging.getLogger(__name__)


class SocketIOClient:
    """
    Thin wrapper around python-socketio Client.
    Runs in its own daemon thread to never block the Qt UI.
    """

    def __init__(
        self,
        server_url: str,
        on_data: Callable[[str, dict], None],
        on_connect: Optional[Callable] = None,
        on_disconnect: Optional[Callable] = None,
        machine_id_field: str = "machine_id",
        default_machine_id: str = "MACHINE-001",
        auto_reconnect: bool = True,
    ):
        self._url               = server_url
        self._on_data           = on_data
        self._on_connect_cb     = on_connect
        self._on_disconnect_cb  = on_disconnect
        self._machine_id_field  = machine_id_field
        self._default_machine_id = default_machine_id
        self._auto_reconnect    = auto_reconnect

        self._sio = sio_lib.Client(
            reconnection=auto_reconnect,
            reconnection_attempts=0,   # infinite
            reconnection_delay=2,
            logger=False,
            engineio_logger=False,
        )
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._register_handlers()

    def _register_handlers(self):
        @self._sio.event
        def connect():
            LOGGER.info("SocketIO connected to %s", self._url)
            if self._on_connect_cb:
                self._on_connect_cb()

        @self._sio.event
        def disconnect():
            LOGGER.warning("SocketIO disconnected")
            if self._on_disconnect_cb:
                self._on_disconnect_cb()

        @self._sio.on("mpu_data")
        def on_mpu_data(data: dict):
            """
            Handles payloads like:
              {'accelX': 872, 'accelY': -56, 'accelZ': -15924,
               'gyroX': -666, 'gyroY': -412, 'gyroZ': -332}
            machine_id field is optional — falls back to default.
            """
            try:
                machine_id = data.get(self._machine_id_field) or self._default_machine_id
                self._on_data(machine_id, data)
            except Exception as e:
                LOGGER.exception("Error processing mpu_data: %s", e)

        @self._sio.on("connect_error")
        def on_connect_error(data):
            LOGGER.error("SocketIO connection error: %s", data)

    def start(self):
        """Start the background connection thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="SocketIOThread")
        self._thread.start()

    def stop(self):
        """Disconnect and stop the thread."""
        self._running = False
        try:
            if self._sio.connected:
                self._sio.disconnect()
        except Exception:
            pass

    def is_connected(self) -> bool:
        return self._sio.connected

    def _run(self):
        while self._running:
            try:
                if not self._sio.connected:
                    LOGGER.info("SocketIO connecting to %s", self._url)
                    self._sio.connect(self._url, transports=["websocket", "polling"])
                    self._sio.wait()  # blocks until disconnected
            except Exception as e:
                LOGGER.exception("SocketIO thread exception: %s", e)

            if self._running and self._auto_reconnect:
                LOGGER.info("SocketIO retrying in 3s")
                time.sleep(3)
            else:
                break
        LOGGER.info("SocketIO thread exiting")
