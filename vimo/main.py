"""
Machine Monitor - Enterprise Desktop Application
Entry point of the application.
"""

import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from ui.main_window import MainWindow
from core.app_config import APP_VERSION, AppConfig
from core.logging_setup import install_exception_hook, setup_logging


def main():
    """Main application entry point."""
    log_file = setup_logging()
    install_exception_hook()
    logger = logging.getLogger(__name__)
    logger.info("Starting Vimo application | log_file=%s", log_file)

    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Vimo")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Hydtech")

    # Load and apply stylesheet
    config = AppConfig()
    stylesheet = config.get_stylesheet()
    app.setStyleSheet(stylesheet)

    window = MainWindow()
    window.show()

    exit_code = app.exec_()
    logger.info("Application exited | code=%s", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
