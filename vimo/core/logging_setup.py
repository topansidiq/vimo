"""
Centralized logging setup for the application.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.runtime_paths import get_log_path

LOG_FILE_NAME = "vimo.log"
MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5


def setup_logging(default_level: str = "INFO") -> Path:
    """
    Configure root logger with console + rotating file handlers.

    Returns the resolved log file path.
    """
    root = logging.getLogger()
    if getattr(root, "_vimo_logging_configured", False):
        return get_log_path(LOG_FILE_NAME)

    level_name = os.getenv("VIMO_LOG_LEVEL", default_level).upper()
    level = getattr(logging, level_name, logging.INFO)
    root.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    log_file = get_log_path(LOG_FILE_NAME)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    root._vimo_logging_configured = True
    logging.getLogger(__name__).info(
        "Logging initialized | level=%s | file=%s",
        logging.getLevelName(level),
        log_file,
    )
    return log_file


def install_exception_hook() -> None:
    """Log uncaught exceptions through the configured logger."""

    def _handle(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger("vimo").exception(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = _handle
