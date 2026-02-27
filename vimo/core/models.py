"""
Data models for sensor readings and machine state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import math


@dataclass
class SensorReading:
    """
    Represents a single MPU6050 sensor reading.
    Menyimpan nilai RAW dan nilai FILTERED (Kalman) secara bersamaan.
    """
    # Raw values (langsung dari sensor)
    accel_x: float
    accel_y: float
    accel_z: float
    gyro_x: float
    gyro_y: float
    gyro_z: float

    # Filtered values (setelah Kalman Filter) - None jika belum diproses
    accel_x_f: Optional[float] = None
    accel_y_f: Optional[float] = None
    accel_z_f: Optional[float] = None
    gyro_x_f:  Optional[float] = None
    gyro_y_f:  Optional[float] = None
    gyro_z_f:  Optional[float] = None

    timestamp:  datetime = field(default_factory=datetime.now)
    machine_id: str = ""

    @classmethod
    def from_dict(cls, data: dict, machine_id: str = "") -> "SensorReading":
        return cls(
            accel_x=float(data.get("accelX", 0)),
            accel_y=float(data.get("accelY", 0)),
            accel_z=float(data.get("accelZ", 0)),
            gyro_x=float(data.get("gyroX", 0)),
            gyro_y=float(data.get("gyroY", 0)),
            gyro_z=float(data.get("gyroZ", 0)),
            machine_id=machine_id,
        )

    def apply_filtered(self, filtered: dict) -> None:
        """Terapkan hasil Kalman Filter ke field _f."""
        self.accel_x_f = filtered.get("accel_x")
        self.accel_y_f = filtered.get("accel_y")
        self.accel_z_f = filtered.get("accel_z")
        self.gyro_x_f  = filtered.get("gyro_x")
        self.gyro_y_f  = filtered.get("gyro_y")
        self.gyro_z_f  = filtered.get("gyro_z")

    # Helper untuk ambil nilai filtered, fallback ke raw
    def _fx(self): return self.accel_x_f if self.accel_x_f is not None else self.accel_x
    def _fy(self): return self.accel_y_f if self.accel_y_f is not None else self.accel_y
    def _fz(self): return self.accel_z_f if self.accel_z_f is not None else self.accel_z
    def _fgx(self): return self.gyro_x_f if self.gyro_x_f is not None else self.gyro_x
    def _fgy(self): return self.gyro_y_f if self.gyro_y_f is not None else self.gyro_y
    def _fgz(self): return self.gyro_z_f if self.gyro_z_f is not None else self.gyro_z

    @property
    def accel_magnitude(self) -> float:
        return math.sqrt(self.accel_x**2 + self.accel_y**2 + self.accel_z**2)

    @property
    def gyro_magnitude(self) -> float:
        return math.sqrt(self.gyro_x**2 + self.gyro_y**2 + self.gyro_z**2)

    @property
    def accel_magnitude_f(self) -> float:
        return math.sqrt(self._fx()**2 + self._fy()**2 + self._fz()**2)

    @property
    def gyro_magnitude_f(self) -> float:
        return math.sqrt(self._fgx()**2 + self._fgy()**2 + self._fgz()**2)

    @property
    def tilt_angle_x(self) -> float:
        try:
            return math.degrees(math.atan2(self._fy(), math.sqrt(self._fx()**2 + self._fz()**2)))
        except ZeroDivisionError:
            return 0.0

    @property
    def tilt_angle_y(self) -> float:
        try:
            return math.degrees(math.atan2(-self._fx(), math.sqrt(self._fy()**2 + self._fz()**2)))
        except ZeroDivisionError:
            return 0.0

    @property
    def vibration_level(self) -> str:
        """
        After auto-calibration, gyro values should be near 0 when static.
        Thresholds are in LSB units (post-calibration):
          - Normal:   |gyro| < 200
          - Elevated: |gyro| < 600
          - High:     |gyro| < 1500
          - Critical: |gyro| >= 1500
        """
        mag = self.gyro_magnitude_f
        if mag < 200:   return "Normal"
        elif mag < 600: return "Elevated"
        elif mag < 1500: return "High"
        else:            return "Critical"

    @property
    def status(self) -> str:
        """
        Status based on POST-CALIBRATION filtered values.
        After auto-zeroing, static sensor should read ~0 on all axes.
        Thresholds:
          - accel magnitude > 3000 LSB from zero = Warning (vibration)
          - accel magnitude > 6000 LSB from zero = Critical
          - gyro magnitude > 600 LSB = Warning
          - gyro magnitude > 1500 LSB = Critical
        """
        if getattr(self, "status_override", None):
            return self.status_override
            
        gm  = self.gyro_magnitude_f
        am  = self.accel_magnitude_f  # after calibration this should be near 0
        if gm > 1500 or am > 6000:   return "Critical"
        elif gm > 600 or am > 3000:  return "Warning"
        return "Normal"

    @property
    def has_filtered(self) -> bool:
        return self.accel_x_f is not None


@dataclass
class MachineState:
    """State mesin yang sedang dimonitor."""
    machine_id: str
    name: str
    location: str = "Plant Floor A"
    is_online: bool = True
    last_reading: Optional[SensorReading] = None
    total_readings: int = 0
    alert_count: int = 0

    @property
    def status(self) -> str:
        if not self.is_online: return "Offline"
        if self.last_reading: return self.last_reading.status
        return "Idle"

    @property
    def status_color(self) -> str:
        return {
            "Normal": "#4caf50", "Warning": "#ff9800",
            "Critical": "#f44336", "Offline": "#9e9e9e", "Idle": "#2196f3",
        }.get(self.status, "#9e9e9e")


def _parse_dt(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now()
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.now()


@dataclass
class DeviceRecord:
    """Metadata for a monitored device."""

    device_id: str
    name: str
    status: str = "Idle"
    location: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceRecord":
        return cls(
            device_id=str(data.get("device_id", data.get("id", ""))).strip(),
            name=str(data.get("name", "")).strip(),
            status=str(data.get("status", "Idle")),
            location=str(data.get("location", "")),
            created_at=_parse_dt(data.get("created_at")),
            updated_at=_parse_dt(data.get("updated_at")),
        )

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "status": self.status,
            "location": self.location,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class AssetRecord:
    """Static asset metadata related to devices."""

    asset_id: str
    name: str
    has_media: bool = False
    path: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_dict(cls, data: dict) -> "AssetRecord":
        return cls(
            asset_id=str(data.get("id", data.get("asset_id", ""))).strip(),
            name=str(data.get("name", "")).strip(),
            has_media=bool(data.get("has_media", False)),
            path=str(data.get("path", "")),
            created_at=_parse_dt(data.get("created_at")),
            updated_at=_parse_dt(data.get("updated_at")),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.asset_id,
            "name": self.name,
            "has_media": self.has_media,
            "path": self.path,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
