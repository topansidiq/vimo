"""
Runtime path helpers.

Target layout:
- <root>/connection.json
- <root>/storage/devices.json
- <root>/storage/assets.json
- <root>/storage/logs/vimo.log
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_RUNTIME_DIR = "VIMO_ROOT"
LEGACY_ENV_RUNTIME_DIR = "VIMO_CONFIG_DIR"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _default_runtime_dir() -> Path:
    """
    Resolve root runtime folder.

    - Frozen build: folder that contains executable
    - Source mode: repository root (.. from vimo/)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_runtime_dir() -> Path:
    """
    Return root runtime directory.

    Priority:
    1. `VIMO_ROOT` environment variable
    2. Auto-detected runtime root
    """
    override = os.getenv(ENV_RUNTIME_DIR, "").strip() or os.getenv(LEGACY_ENV_RUNTIME_DIR, "").strip()
    root = Path(override).expanduser().resolve() if override else _default_runtime_dir()
    return _ensure_dir(root)


def get_config_dir() -> Path:
    """
    Keep config directly at runtime root, as requested.
    """
    return get_runtime_dir()


def get_storage_dir() -> Path:
    return _ensure_dir(get_runtime_dir() / "storage")


def get_data_dir() -> Path:
    return get_storage_dir()


def get_logs_dir() -> Path:
    return _ensure_dir(get_storage_dir() / "logs")


def get_config_path(filename: str) -> Path:
    return get_config_dir() / filename


def get_data_path(filename: str) -> Path:
    return get_data_dir() / filename


def get_log_path(filename: str) -> Path:
    return get_logs_dir() / filename
