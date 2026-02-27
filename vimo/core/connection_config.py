"""
Connection configuration read/write utilities.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from core.runtime_paths import get_config_path

LOGGER = logging.getLogger(__name__)

_LEGACY_CONFIG_PATH = Path(__file__).with_name("connection.json")
_CONFIG_PATH = get_config_path("connection.json")

_DEFAULTS = {
    "host": "127.0.0.1",
    "port": 5000,
    # Alert thresholds
    "gyro_warn": 1000,
    "gyro_crit": 2000,
    "accel_warn": 10000,
    "accel_crit": 15000,
    # Data settings
    "buffer_size": 500,
    "poll_rate": 5,
    "log_enabled": True,
    "auto_reconnect": True,
    # Processing settings
    "norm_range": 0,
    "ai_enabled": True,
    "ai_sensitivity": 3.0,
}


def _safe_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return max(low, min(high, parsed))


def _safe_float(value: Any, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    return max(low, min(high, parsed))


def _normalize(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Merge payload with defaults and enforce safe types/ranges."""
    merged = dict(_DEFAULTS)
    merged.update(cfg or {})

    host = str(merged.get("host", _DEFAULTS["host"])).strip()
    if host.startswith("http://"):
        host = host[len("http://"):]
    elif host.startswith("https://"):
        host = host[len("https://"):]
    host = host.strip("/")
    if not host:
        host = _DEFAULTS["host"]

    return {
        "host": host,
        "port": _safe_int(merged.get("port"), _DEFAULTS["port"], 1, 65535),
        "gyro_warn": _safe_int(merged.get("gyro_warn"), _DEFAULTS["gyro_warn"], 0, 100000),
        "gyro_crit": _safe_int(merged.get("gyro_crit"), _DEFAULTS["gyro_crit"], 0, 100000),
        "accel_warn": _safe_int(merged.get("accel_warn"), _DEFAULTS["accel_warn"], 0, 100000),
        "accel_crit": _safe_int(merged.get("accel_crit"), _DEFAULTS["accel_crit"], 0, 100000),
        "buffer_size": _safe_int(merged.get("buffer_size"), _DEFAULTS["buffer_size"], 10, 50000),
        "poll_rate": _safe_int(merged.get("poll_rate"), _DEFAULTS["poll_rate"], 1, 1000),
        "log_enabled": bool(merged.get("log_enabled", _DEFAULTS["log_enabled"])),
        "auto_reconnect": bool(merged.get("auto_reconnect", _DEFAULTS["auto_reconnect"])),
        "norm_range": _safe_int(merged.get("norm_range"), _DEFAULTS["norm_range"], 0, 32768),
        "ai_enabled": bool(merged.get("ai_enabled", _DEFAULTS["ai_enabled"])),
        "ai_sensitivity": _safe_float(
            merged.get("ai_sensitivity"),
            _DEFAULTS["ai_sensitivity"],
            1.0,
            10.0,
        ),
    }


def _bootstrap_legacy_config() -> None:
    """
    Migrate legacy config to runtime config path once.
    """
    if _CONFIG_PATH.exists():
        return

    candidates = [
        _LEGACY_CONFIG_PATH,
        _legacy_os_config_path(),
    ]
    source = next((p for p in candidates if p and p.exists()), None)
    if source is None:
        return

    try:
        with source.open("r", encoding="utf-8") as src:
            payload = json.load(src)
        normalized = _normalize(payload)
        _write_config(normalized)
        LOGGER.info("Migrated config from %s to %s", source, _CONFIG_PATH)
    except Exception as exc:
        LOGGER.warning("Failed to migrate legacy config: %s", exc)


def _legacy_os_config_path() -> Optional[Path]:
    """
    Previous production path used before runtime moved to root.
    """
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "Vimo" / "config" / "connection.json"

    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "Vimo" / "config" / "connection.json"

    return Path.home() / ".config" / "Vimo" / "config" / "connection.json"


def _write_config(cfg: Dict[str, Any]) -> None:
    temp_path = _CONFIG_PATH.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, sort_keys=True)
        fh.write("\n")
    temp_path.replace(_CONFIG_PATH)


def load() -> dict:
    """Load config from disk and merge with defaults."""
    _bootstrap_legacy_config()

    if _CONFIG_PATH.exists():
        try:
            with _CONFIG_PATH.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
            if isinstance(payload, dict):
                return _normalize(payload)
            LOGGER.warning("Config payload is not an object; using defaults")
        except Exception as exc:
            LOGGER.warning("Failed to read config from %s: %s", _CONFIG_PATH, exc)

    return dict(_DEFAULTS)


def save(cfg: dict) -> bool:
    """Persist config to runtime directory."""
    try:
        normalized = _normalize(cfg)
        _write_config(normalized)
        return True
    except Exception as exc:
        LOGGER.error("Failed to save config to %s: %s", _CONFIG_PATH, exc)
        return False


def get_server_url(cfg: dict = None) -> str:
    """Build base URL from config."""
    if cfg is None:
        cfg = load()
    normalized = _normalize(cfg)
    return f"http://{normalized['host']}:{normalized['port']}"
