"""
Data manager for real-time ingestion, device/asset CRUD, and UI distribution.
"""

import json
import os
import threading
import logging
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from core import connection_config
from core import runtime_paths
from core.kalman_filter import IMUKalmanFilter
from core.ai_analyzer import VimoAIAnalyzer
from core.mqtt_client import MQTTClient
from core.socketio_client import SocketIOClient
from core.models import AssetRecord, DeviceRecord, MachineState, SensorReading
from core.server_api_client import ServerAPIClient

LOGGER = logging.getLogger(__name__)


class DataBuffer:
    """Thread-safe circular buffer for sensor readings."""

    def __init__(self, maxlen: int = 500):
        self._buffer: deque = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def append(self, reading: SensorReading):
        with self._lock:
            self._buffer.append(reading)

    def get_all(self) -> List[SensorReading]:
        with self._lock:
            return list(self._buffer)

    def get_latest(self, n: int = 1) -> List[SensorReading]:
        with self._lock:
            data = list(self._buffer)
            return data[-n:] if len(data) >= n else data

    def clear(self):
        with self._lock:
            self._buffer.clear()

    def resize(self, maxlen: int):
        with self._lock:
            self._buffer = deque(self._buffer, maxlen=maxlen)

    def __len__(self):
        with self._lock:
            return len(self._buffer)


class DataManager(QObject):
    """Central manager for data stream, device metadata, and assets."""

    data_updated = pyqtSignal(str, object)             # machine_id, SensorReading
    machine_status_changed = pyqtSignal(str, str)      # machine_id, status
    connection_status_changed = pyqtSignal(bool)       # is_connected
    alert_triggered = pyqtSignal(str, str, str)        # machine_id, level, message
    log_entry_added = pyqtSignal(dict)                 # log entry
    devices_changed = pyqtSignal()                     # device CRUD changed
    assets_changed = pyqtSignal()                      # asset CRUD changed

    UI_UPDATE_INTERVAL_MS = 50
    ALERT_DEBOUNCE_SECONDS = 3.0

    DEVICES_FILE = runtime_paths.get_data_path("devices.json")
    ASSETS_FILE = runtime_paths.get_data_path("assets.json")

    _ALLOWED_STATUS = {"Idle", "Normal", "Warning", "Critical", "Offline"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._is_connected = False

        self._devices: Dict[str, DeviceRecord] = {}
        self._assets: Dict[str, AssetRecord] = {}

        self._machines: Dict[str, MachineState] = {}
        self._buffers: Dict[str, DataBuffer] = {}
        self._kalmans: Dict[str, IMUKalmanFilter] = {}
        self._analyzers: Dict[str, VimoAIAnalyzer] = {}

        self._logs: List[dict] = []
        self._pending: Dict[str, SensorReading] = {}
        self._last_alert: Dict[str, datetime] = {}

        self._offsets: Dict[str, List[float]] = {}
        self._cal_samples: Dict[str, List[dict]] = {}
        self._cal_needed = 15

        self._mqtt_client: Optional[MQTTClient] = None
        self._sio_client: Optional[SocketIOClient] = None
        self._server_client: Optional[ServerAPIClient] = None
        self._topic_to_device: Dict[str, str] = {}

        self._runtime_cfg: Dict[str, Any] = connection_config.load()
        self._buffer_maxlen = int(self._runtime_cfg.get("buffer_size", 500))

        self._load_devices()
        self._load_assets()
        self._build_runtime_from_devices()

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._dispatch_pending)
        self._ui_timer.start(self.UI_UPDATE_INTERVAL_MS)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def reload_runtime_config(self, cfg: Optional[dict] = None) -> dict:
        """
        Reload config from disk and apply runtime-only changes.
        If cfg is provided, persist it first.
        """
        if cfg is not None:
            connection_config.save(cfg)

        loaded = connection_config.load()
        new_maxlen = int(loaded.get("buffer_size", 500))

        with self._lock:
            self._runtime_cfg = loaded
            if new_maxlen != self._buffer_maxlen:
                self._buffer_maxlen = new_maxlen
                for buffer in self._buffers.values():
                    buffer.resize(self._buffer_maxlen)

        return dict(self._runtime_cfg)

    @staticmethod
    def _write_json_atomic(path, payload: list) -> None:
        temp = str(path) + ".tmp"
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
        os.replace(temp, path)

    def _load_devices(self) -> None:
        loaded: Dict[str, DeviceRecord] = {}
        if os.path.exists(self.DEVICES_FILE):
            try:
                with open(self.DEVICES_FILE, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, list):
                    for row in payload:
                        rec = DeviceRecord.from_dict(row)
                        if rec.device_id:
                            loaded[rec.device_id] = rec
            except Exception as exc:
                self._add_log("ERROR", "System", f"Failed to load devices.json: {exc}")
        self._devices = loaded

    def _save_devices(self) -> None:
        data = [r.to_dict() for r in self._sorted_devices()]
        self._write_json_atomic(self.DEVICES_FILE, data)

    def _load_assets(self) -> None:
        loaded: Dict[str, AssetRecord] = {}
        if os.path.exists(self.ASSETS_FILE):
            try:
                with open(self.ASSETS_FILE, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, list):
                    for row in payload:
                        rec = AssetRecord.from_dict(row)
                        if rec.asset_id:
                            loaded[rec.asset_id] = rec
            except Exception as exc:
                self._add_log("ERROR", "System", f"Failed to load assets.json: {exc}")
        self._assets = loaded

    def _save_assets(self) -> None:
        data = [r.to_dict() for r in self._sorted_assets()]
        self._write_json_atomic(self.ASSETS_FILE, data)

    def _build_runtime_from_devices(self) -> None:
        self._machines.clear()
        self._buffers.clear()
        self._kalmans.clear()

        for device in self._sorted_devices():
            self._machines[device.device_id] = MachineState(
                machine_id=device.device_id,
                name=device.name,
                location=device.location,
                is_online=device.status != "Offline",
            )
            self._buffers[device.device_id] = DataBuffer(maxlen=self._buffer_maxlen)
            self._kalmans[device.device_id] = IMUKalmanFilter()
            self._analyzers[device.device_id] = VimoAIAnalyzer()

    # ------------------------------------------------------------------
    # Public CRUD API - Devices
    # ------------------------------------------------------------------

    def list_devices(self) -> List[dict]:
        with self._lock:
            return [d.to_dict() for d in self._sorted_devices()]

    def get_device(self, device_id: str) -> Optional[dict]:
        with self._lock:
            rec = self._devices.get(device_id)
            return rec.to_dict() if rec else None

    def create_device(
        self,
        device_id: str,
        name: str,
        location: str = "",
        status: str = "Idle",
    ) -> Tuple[bool, str]:
        device_id = (device_id or "").strip()
        name = (name or "").strip()
        if not device_id:
            return False, "device_id wajib diisi"
        if not name:
            return False, "name wajib diisi"

        now = datetime.now()
        with self._lock:
            if device_id in self._devices:
                return False, f"Device '{device_id}' sudah ada"

            rec = DeviceRecord(
                device_id=device_id,
                name=name,
                status=self._normalize_status(status),
                location=(location or "").strip(),
                created_at=now,
                updated_at=now,
            )
            self._devices[device_id] = rec
            self._machines[device_id] = MachineState(
                machine_id=device_id,
                name=rec.name,
                location=rec.location,
                is_online=rec.status != "Offline",
            )
            self._buffers[device_id] = DataBuffer(maxlen=self._buffer_maxlen)
            self._kalmans[device_id] = IMUKalmanFilter()
            self._analyzers[device_id] = VimoAIAnalyzer()

            self._save_devices()

        self.devices_changed.emit()
        self._add_log("INFO", "Device", f"Created device: {device_id}")
        return True, "Device berhasil ditambahkan"

    def update_device(
        self,
        current_device_id: str,
        new_device_id: str,
        name: str,
        location: str,
        status: str,
    ) -> Tuple[bool, str]:
        current_device_id = (current_device_id or "").strip()
        new_device_id = (new_device_id or "").strip()
        name = (name or "").strip()

        if not current_device_id:
            return False, "Device yang akan diupdate tidak valid"
        if not new_device_id:
            return False, "device_id wajib diisi"
        if not name:
            return False, "name wajib diisi"

        with self._lock:
            rec = self._devices.get(current_device_id)
            if not rec:
                return False, f"Device '{current_device_id}' tidak ditemukan"

            if new_device_id != current_device_id and new_device_id in self._devices:
                return False, f"Device '{new_device_id}' sudah ada"

            rename = new_device_id != current_device_id
            now = datetime.now()

            if rename:
                self._devices.pop(current_device_id)
                rec.device_id = new_device_id
                self._devices[new_device_id] = rec

                machine = self._machines.pop(current_device_id, None)
                if machine:
                    machine.machine_id = new_device_id
                    self._machines[new_device_id] = machine

                buf = self._buffers.pop(current_device_id, None)
                if buf:
                    self._buffers[new_device_id] = buf

                kalman = self._kalmans.pop(current_device_id, None)
                if kalman:
                    self._kalmans[new_device_id] = kalman
                    
                analyzer = self._analyzers.pop(current_device_id, None)
                if analyzer:
                    self._analyzers[new_device_id] = analyzer

                if current_device_id in self._offsets:
                    self._offsets[new_device_id] = self._offsets.pop(current_device_id)
                if current_device_id in self._cal_samples:
                    self._cal_samples[new_device_id] = self._cal_samples.pop(current_device_id)
                if current_device_id in self._pending:
                    self._pending[new_device_id] = self._pending.pop(current_device_id)
                if current_device_id in self._last_alert:
                    self._last_alert[new_device_id] = self._last_alert.pop(current_device_id)

            rec.name = name
            rec.location = (location or "").strip()
            rec.status = self._normalize_status(status)
            rec.updated_at = now

            machine = self._machines.get(new_device_id)
            if machine:
                machine.name = rec.name
                machine.location = rec.location
                machine.is_online = rec.status != "Offline"

            self._save_devices()

        self.devices_changed.emit()
        self._add_log("INFO", "Device", f"Updated device: {new_device_id}")
        return True, "Device berhasil diupdate"

    def delete_device(self, device_id: str) -> Tuple[bool, str]:
        device_id = (device_id or "").strip()
        if not device_id:
            return False, "device_id tidak valid"

        with self._lock:
            if device_id not in self._devices:
                return False, f"Device '{device_id}' tidak ditemukan"

            self._devices.pop(device_id, None)
            self._machines.pop(device_id, None)
            self._buffers.pop(device_id, None)
            self._kalmans.pop(device_id, None)
            self._analyzers.pop(device_id, None)
            self._offsets.pop(device_id, None)
            self._cal_samples.pop(device_id, None)
            self._pending.pop(device_id, None)
            self._last_alert.pop(device_id, None)

            self._save_devices()

        self.devices_changed.emit()
        self._add_log("INFO", "Device", f"Deleted device: {device_id}")
        return True, "Device berhasil dihapus"

    # ------------------------------------------------------------------
    # Public CRUD API - Assets
    # ------------------------------------------------------------------

    def list_assets(self) -> List[dict]:
        with self._lock:
            return [a.to_dict() for a in self._sorted_assets()]

    def get_asset(self, asset_id: str) -> Optional[dict]:
        with self._lock:
            rec = self._assets.get(asset_id)
            return rec.to_dict() if rec else None

    def create_asset(
        self,
        asset_id: str,
        name: str,
        has_media: bool,
        path: str,
    ) -> Tuple[bool, str]:
        asset_id = (asset_id or "").strip()
        name = (name or "").strip()
        if not asset_id:
            return False, "id wajib diisi"
        if not name:
            return False, "name wajib diisi"

        now = datetime.now()
        with self._lock:
            if asset_id in self._assets:
                return False, f"Asset '{asset_id}' sudah ada"

            rec = AssetRecord(
                asset_id=asset_id,
                name=name,
                has_media=bool(has_media),
                path=(path or "").strip(),
                created_at=now,
                updated_at=now,
            )
            self._assets[asset_id] = rec
            self._save_assets()

        self.assets_changed.emit()
        self._add_log("INFO", "Asset", f"Created asset: {asset_id}")
        return True, "Asset berhasil ditambahkan"

    def update_asset(
        self,
        current_asset_id: str,
        new_asset_id: str,
        name: str,
        has_media: bool,
        path: str,
    ) -> Tuple[bool, str]:
        current_asset_id = (current_asset_id or "").strip()
        new_asset_id = (new_asset_id or "").strip()
        name = (name or "").strip()

        if not current_asset_id:
            return False, "Asset yang akan diupdate tidak valid"
        if not new_asset_id:
            return False, "id wajib diisi"
        if not name:
            return False, "name wajib diisi"

        with self._lock:
            rec = self._assets.get(current_asset_id)
            if not rec:
                return False, f"Asset '{current_asset_id}' tidak ditemukan"

            if new_asset_id != current_asset_id and new_asset_id in self._assets:
                return False, f"Asset '{new_asset_id}' sudah ada"

            if new_asset_id != current_asset_id:
                self._assets.pop(current_asset_id)
                rec.asset_id = new_asset_id
                self._assets[new_asset_id] = rec

            rec.name = name
            rec.has_media = bool(has_media)
            rec.path = (path or "").strip()
            rec.updated_at = datetime.now()

            self._save_assets()

        self.assets_changed.emit()
        self._add_log("INFO", "Asset", f"Updated asset: {new_asset_id}")
        return True, "Asset berhasil diupdate"

    def delete_asset(self, asset_id: str) -> Tuple[bool, str]:
        asset_id = (asset_id or "").strip()
        if not asset_id:
            return False, "id tidak valid"

        with self._lock:
            if asset_id not in self._assets:
                return False, f"Asset '{asset_id}' tidak ditemukan"

            self._assets.pop(asset_id, None)
            self._save_assets()

        self.assets_changed.emit()
        self._add_log("INFO", "Asset", f"Deleted asset: {asset_id}")
        return True, "Asset berhasil dihapus"

    # ------------------------------------------------------------------
    # Connection and ingest API
    # ------------------------------------------------------------------

    def connect_server(self, cfg: dict = None):
        """Connect to server: discover devices via HTTP, then ingest via SocketIO (WS)."""
        cfg = self.reload_runtime_config(cfg)

        self.disconnect_server()
        server_url = connection_config.get_server_url(cfg)

        auto_rc = bool(cfg.get("auto_reconnect", True))

        # 1. Fetch devices via REST API first to sync metadata
        self._server_client = ServerAPIClient(server_url)
        try:
            remote_devices = self._server_client.fetch_devices()
            self._sync_devices_from_server(remote_devices)
            LOGGER.info("Received %s devices from API", len(remote_devices))
        except Exception as exc:
            self._add_log("ERROR", "System", f"Failed to fetch devices: {exc}")
            # we continue anyway, might have local devices already

        # 2. Connect via SocketIO for real-time stream
        self._sio_client = SocketIOClient(
            server_url=server_url,
            on_data=self.ingest_dict,
            on_connect=self._on_server_connected,
            on_disconnect=self._on_server_disconnected,
            machine_id_field="device_id",
            auto_reconnect=auto_rc
        )
        self._sio_client.start()

        self._add_log(
            "INFO",
            "System",
            f"Connecting to Server (SocketIO) at {server_url}",
        )

    def disconnect_server(self):
        """Disconnect from server."""
        if self._mqtt_client:
            self._mqtt_client.stop()
            self._mqtt_client = None

        if self._sio_client:
            self._sio_client.stop()
            self._sio_client = None

        was_connected = self._is_connected
        self._is_connected = False
        self._server_client = None
        self._topic_to_device = {}
        self._set_all_devices_offline()
        if was_connected:
            self.connection_status_changed.emit(False)
            self._add_log("INFO", "System", "Disconnected from server")

    def _on_server_connected(self):
        self._is_connected = True
        self.connection_status_changed.emit(True)
        self._add_log("INFO", "System", "Connected to server")

    def _on_server_disconnected(self):
        self._is_connected = False
        self._set_all_devices_offline()
        self.connection_status_changed.emit(False)
        self._add_log("WARN", "System", "Disconnected from server")

    def ingest_raw(self, machine_id: str, raw_data: str):
        """Ingest a JSON string payload."""
        try:
            data = json.loads(raw_data)
            self.ingest_dict(machine_id, data)
        except json.JSONDecodeError as exc:
            self._add_log("ERROR", machine_id, f"JSON parse error: {exc}")

    def _on_mqtt_data(self, topic: str, payload: dict):
        """Handle parsed MQTT JSON payload."""
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if not isinstance(data, dict):
            return

        machine_id = self._resolve_machine_id(topic, payload)
        if not machine_id:
            machine_id = self._resolve_machine_id(topic, data)
        if not machine_id:
            return
        self.ingest_dict(machine_id, data)

    def ingest_dict(self, machine_id: str, data: dict):
        """Ingest sensor payload and process with calibration + Kalman filter."""
        # Handle nesting (Socket.IO relay)
        if isinstance(data.get("data"), dict):
            data = data["data"]

        # Support both full names and abbreviated names (ESP32)
        v_ax = data.get("accelX", data.get("ax", 0))
        v_ay = data.get("accelY", data.get("ay", 0))
        v_az = data.get("accelZ", data.get("az", 0))
        v_gx = data.get("gyroX",  data.get("gx", 0))
        v_gy = data.get("gyroY",  data.get("gy", 0))
        v_gz = data.get("gyroZ",  data.get("gz", 0))
        
        # Apply normalization if activated -> maps [-32768, 32767] relative to norm_range
        cfg = self._runtime_cfg
        n_rng = cfg.get("norm_range", 0)
        if n_rng > 0:
            scale = n_rng / 32768.0
            v_ax *= scale
            v_ay *= scale
            v_az *= scale
            v_gx *= scale
            v_gy *= scale
            v_gz *= scale

        norm_data = {
            "accelX": v_ax,
            "accelY": v_ay,
            "accelZ": v_az,
            "gyroX":  v_gx,
            "gyroY":  v_gy,
            "gyroZ":  v_gz,
        }
        data = norm_data

        machine_id = (machine_id or "").strip()
        if not machine_id:
            return

        if machine_id not in self._machines:
            self.create_device(
                device_id=machine_id,
                name=f"Auto {machine_id}",
                location="",
                status="Idle",
            )

        self._update_device_runtime(machine_id, status=None)

        # Startup auto-zero calibration
        if machine_id not in self._offsets:
            samples = self._cal_samples.get(machine_id, [])
            samples.append(data.copy())
            self._cal_samples[machine_id] = samples

            if len(samples) >= self._cal_needed:
                avg_ax = sum(s.get("accelX", 0) for s in samples) / len(samples)
                avg_ay = sum(s.get("accelY", 0) for s in samples) / len(samples)
                avg_az = sum(s.get("accelZ", 0) for s in samples) / len(samples)
                avg_gx = sum(s.get("gyroX", 0) for s in samples) / len(samples)
                avg_gy = sum(s.get("gyroY", 0) for s in samples) / len(samples)
                avg_gz = sum(s.get("gyroZ", 0) for s in samples) / len(samples)

                with self._lock:
                    self._offsets[machine_id] = [avg_ax, avg_ay, avg_az, avg_gx, avg_gy, avg_gz]

                self._add_log("INFO", machine_id, "Automatic startup zeroing complete")
                self._cal_samples.pop(machine_id, None)
            return

        offsets = self._offsets.get(machine_id, [0.0] * 6)
        corrected = {
            "accelX": data.get("accelX", 0) - offsets[0],
            "accelY": data.get("accelY", 0) - offsets[1],
            "accelZ": data.get("accelZ", 0) - offsets[2],
            "gyroX": data.get("gyroX", 0) - offsets[3],
            "gyroY": data.get("gyroY", 0) - offsets[4],
            "gyroZ": data.get("gyroZ", 0) - offsets[5],
        }

        reading = SensorReading.from_dict(corrected, machine_id)

        kalman = self._kalmans.get(machine_id)
        if kalman:
            raw_vals = {
                "accel_x": reading.accel_x,
                "accel_y": reading.accel_y,
                "accel_z": reading.accel_z,
                "gyro_x": reading.gyro_x,
                "gyro_y": reading.gyro_y,
                "gyro_z": reading.gyro_z,
            }
            filtered = kalman.process(raw_vals)
            reading.apply_filtered(filtered)

        self._store_reading(machine_id, reading)

    def tune_kalman(
        self,
        machine_id: str,
        accel_q=None,
        accel_r=None,
        gyro_q=None,
        gyro_r=None,
    ):
        """Tune Kalman params at runtime."""
        kalman = self._kalmans.get(machine_id)
        if kalman:
            kalman.tune(accel_q=accel_q, accel_r=accel_r, gyro_q=gyro_q, gyro_r=gyro_r)

    def calibrate(self, machine_id: str):
        """Zeroing sensor using average of latest readings."""
        buffer = self.get_buffer(machine_id)
        if not buffer or len(buffer) < 10:
            self._add_log("WARN", machine_id, "Calibration failed: not enough data")
            return

        readings = buffer.get_latest(20)
        avg_ax = sum(r.accel_x for r in readings) / len(readings)
        avg_ay = sum(r.accel_y for r in readings) / len(readings)
        avg_az = sum(r.accel_z for r in readings) / len(readings)
        avg_gx = sum(r.gyro_x for r in readings) / len(readings)
        avg_gy = sum(r.gyro_y for r in readings) / len(readings)
        avg_gz = sum(r.gyro_z for r in readings) / len(readings)

        with self._lock:
            old_off = self._offsets.get(machine_id, [0.0] * 6)
            self._offsets[machine_id] = [
                old_off[0] + avg_ax,
                old_off[1] + avg_ay,
                old_off[2] + avg_az,
                old_off[3] + avg_gx,
                old_off[4] + avg_gy,
                old_off[5] + avg_gz,
            ]

        self._add_log("INFO", machine_id, "Sensors zeroed successfully")

    # ------------------------------------------------------------------
    # Read APIs used by UI pages
    # ------------------------------------------------------------------

    def get_machine(self, machine_id: str) -> Optional[MachineState]:
        return self._machines.get(machine_id)

    def get_all_machines(self) -> List[MachineState]:
        with self._lock:
            return [self._machines[d.device_id] for d in self._sorted_devices() if d.device_id in self._machines]

    def get_buffer(self, machine_id: str) -> Optional[DataBuffer]:
        return self._buffers.get(machine_id)

    def get_logs(self, limit: int = 200) -> List[dict]:
        return self._logs[-limit:]

    def get_kalman_gains(self, machine_id: str) -> Optional[dict]:
        kalman = self._kalmans.get(machine_id)
        return kalman.get_gains() if kalman else None

    def clear_all_data(self):
        with self._lock:
            for buffer in self._buffers.values():
                buffer.clear()
            for machine in self._machines.values():
                machine.last_reading = None
                machine.total_readings = 0
                machine.alert_count = 0
            for device in self._devices.values():
                if device.status != "Offline":
                    device.status = "Idle"
                device.updated_at = datetime.now()

            self._pending.clear()
            self._last_alert.clear()
            self._offsets.clear()
            self._cal_samples.clear()
            self._logs = []

        self._add_log("INFO", "System", "All monitoring data cleared")

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _store_reading(self, machine_id: str, reading: SensorReading):
        with self._lock:
            machine = self._machines.get(machine_id)
            if not machine:
                return

            prev_status = machine.status
            machine.is_online = True
            machine.last_reading = reading
            machine.total_readings += 1
            self._buffers[machine_id].append(reading)
            self._pending[machine_id] = reading

            new_status = machine.status
            
            # --- AI ANOMALY DETECTION INSTEAD OF STATIC THRESHOLD ---
            cfg = self._runtime_cfg
            ai_enabled = cfg.get("ai_enabled", True)
            
            if ai_enabled and (machine_id in self._analyzers):
                analyzer = self._analyzers[machine_id]
                ai_result = analyzer.analyze(
                    accel_mag=reading.accel_magnitude_f, 
                    gyro_mag=reading.gyro_magnitude_f,
                    sensitivity=cfg.get("ai_sensitivity", 3.0)
                )
                
                # We can store the AI score in the reading for future reference if needed
                # reading.ai_score = max(ai_result['accel_z'], ai_result['gyro_z'])
                
                if ai_result["is_anomaly"]:
                    # Anomaly detected! Decide if it's Warning or Critical
                    # As a heuristic, if Z-score > sensitivity * 1.5, it's Critical
                    sens = cfg.get("ai_sensitivity", 3.0)
                    z_max = max(ai_result["accel_z"], ai_result["gyro_z"])
                    
                    new_status = "Critical" if z_max > (sens * 1.5) else "Warning"
                    reading.status_override = new_status
                else:
                    new_status = "Normal"
                    reading.status_override = new_status
            else:
                # Fallback to simple static thresholds if AI is disabled
                 gyro_w = cfg.get("gyro_warn", 1000)
                 gyro_c = cfg.get("gyro_crit", 2000)
                 accel_w = cfg.get("accel_warn", 10000)
                 accel_c = cfg.get("accel_crit", 15000)
                 
                 g_mag = reading.gyro_magnitude_f
                 a_mag = reading.accel_magnitude_f
                 
                 if g_mag > gyro_c or a_mag > accel_c:
                     new_status = "Critical"
                 elif g_mag > gyro_w or a_mag > accel_w:
                     new_status = "Warning"
                 else:
                     new_status = "Normal"
                 
                 reading.status_override = new_status

            self._update_device_runtime_locked(
                machine_id,
                status=new_status,
            )

            if new_status != prev_status:
                self.machine_status_changed.emit(machine_id, new_status)
                lvl = "WARN" if new_status == "Warning" else "CRITICAL" if new_status == "Critical" else "INFO"
                self._add_log(lvl, machine_id, f"Status changed: {prev_status} -> {new_status}")

            if new_status in ("Warning", "Critical"):
                now = datetime.now()
                last = self._last_alert.get(machine_id)
                if last is None or (now - last).total_seconds() >= self.ALERT_DEBOUNCE_SECONDS:
                    self._last_alert[machine_id] = now
                    machine.alert_count += 1
                    
                    msg = "Anomaly detected by AI" if ai_enabled else f"High magnitude: G={reading.gyro_magnitude_f:.0f}"
                    if ai_enabled:
                         msg = ai_result.get("message", msg)

                    self.alert_triggered.emit(
                        machine_id,
                        new_status,
                        msg,
                    )

    def _dispatch_pending(self):
        with self._lock:
            pending = dict(self._pending)
            self._pending.clear()

        for machine_id, reading in pending.items():
            self.data_updated.emit(machine_id, reading)

    def _update_device_runtime(self, machine_id: str, status: Optional[str]):
        with self._lock:
            self._update_device_runtime_locked(machine_id, status)

    def _update_device_runtime_locked(self, machine_id: str, status: Optional[str]):
        rec = self._devices.get(machine_id)
        if not rec:
            return
        if status:
            rec.status = self._normalize_status(status)
        rec.updated_at = datetime.now()

    def _add_log(self, level: str, source: str, message: str):
        level = (level or "INFO").upper()
        if not self._runtime_cfg.get("log_enabled", True) and level not in {"ERROR", "CRITICAL"}:
            return

        py_level = {
            "INFO": logging.INFO,
            "WARN": logging.WARNING,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }.get(level, logging.INFO)
        LOGGER.log(py_level, "%s | %s", source, message)

        entry = {
            "timestamp": datetime.now(),
            "level": level,
            "source": source,
            "message": message,
        }
        self._logs.append(entry)
        if len(self._logs) > 5000:
            self._logs = self._logs[-2500:]
        self.log_entry_added.emit(entry)

    def _set_all_devices_offline(self):
        with self._lock:
            now = datetime.now()
            for machine_id, machine in self._machines.items():
                machine.is_online = False
                rec = self._devices.get(machine_id)
                if rec:
                    rec.status = "Offline"
                    rec.updated_at = now
        self.devices_changed.emit()

    def _normalize_status(self, status: Optional[str]) -> str:
        status = (status or "Idle").strip()
        return status if status in self._ALLOWED_STATUS else "Idle"

    def _sync_devices_from_server(self, remote_devices: List[dict]):
        """Sync local devices with remote server devices metadata."""
        count = 0
        updated = 0
        LOGGER.info("Syncing %s devices from server", len(remote_devices))
        
        with self._lock:
            for dev_dict in remote_devices:
                # Support both 'device_id' and 'id' from server
                device_id = str(dev_dict.get("device_id", dev_dict.get("id", ""))).strip()
                if not device_id:
                    LOGGER.warning("Skipping device without ID: %s", dev_dict)
                    continue
                
                rec = DeviceRecord.from_dict(dev_dict)
                
                if device_id not in self._devices:
                    # Create new
                    self._devices[device_id] = rec
                    self._machines[device_id] = MachineState(
                        machine_id=device_id,
                        name=rec.name,
                        location=rec.location,
                        is_online=True
                    )
                    self._buffers[device_id] = DataBuffer(maxlen=self._buffer_maxlen)
                    self._kalmans[device_id] = IMUKalmanFilter()
                    self._analyzers[device_id] = VimoAIAnalyzer()
                    count += 1
                    LOGGER.info("Added new device from server: %s", device_id)
                else:
                    # Update existing metadata
                    local_rec = self._devices[device_id]
                    local_rec.name = rec.name
                    local_rec.location = rec.location
                    
                    machine = self._machines.get(device_id)
                    if machine:
                        machine.name = rec.name
                        machine.location = rec.location
                    updated += 1
            
            # Save if anything changed
            if count > 0 or updated > 0:
                self._save_devices()
                msg = f"Sync complete: {count} new, {updated} updated"
                self._add_log("INFO", "System", msg)
                LOGGER.info(msg)
            else:
                LOGGER.info("Device sync resulted in no changes")
        
        if count > 0 or updated > 0:
            self.devices_changed.emit()

    def _build_topic_map(self, devices: List[dict]) -> Dict[str, str]:
        """Create a mapping of MQTT topics to local device IDs."""
        mapping = {}
        for dev in devices:
            device_id = dev.get("device_id")
            if not device_id:
                continue
            # Use custom topic if provided, else default to vimo/machine/{id}
            topic = dev.get("mqtt_topic") or f"vimo/machine/{device_id}"
            mapping[topic] = device_id
        return mapping

    def _resolve_machine_id(self, topic: str, data: dict) -> Optional[str]:
        """Resolve which machine_id this data belongs to."""
        # Try mapped topic first
        if topic in self._topic_to_device:
            return self._topic_to_device[topic]
        
        # Then check for explicit field in payload
        mid = data.get("machine_id") or data.get("device_id")
        if mid:
            return str(mid).strip()
            
        return None

    def _sorted_devices(self) -> List[DeviceRecord]:
        return sorted(self._devices.values(), key=lambda x: x.device_id)

    def _sorted_assets(self) -> List[AssetRecord]:
        return sorted(self._assets.values(), key=lambda x: x.asset_id)
