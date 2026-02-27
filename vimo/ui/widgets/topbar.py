"""
Top bar widget - shows title and quick status indicators.
"""

from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget
import qtawesome as qta

from core.app_config import AppConfig
from core.data_manager import DataManager


def _icon(name, color="#9e9e9e"):
    try:
        return qta.icon(name, color=color)
    except Exception:
        return None


class TopBar(QWidget):
    """Application top bar with page title and status indicators."""

    fullscreen_requested = pyqtSignal()

    def __init__(self, data_manager: DataManager, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self.data_manager = data_manager
        self._alert_count = 0

        self.setFixedHeight(self.config.LAYOUT["topbar_height"])
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {self.config.COLORS['bg_topbar']};
                border-bottom: 1px solid {self.config.COLORS['border']};
            }}
            """
        )

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        self.title_label = QLabel("Dashboard")
        self.title_label.setStyleSheet(
            f"""
            color: {self.config.COLORS['text_primary']};
            font-size: 14px;
            font-weight: bold;
            background: transparent;
            border: none;
            """
        )
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.alert_badge = QLabel("* 0 Alerts")
        self.alert_badge.setStyleSheet(
            f"""
            color: {self.config.COLORS['text_muted']};
            font-size: 10px;
            background: transparent;
            border: none;
            """
        )
        layout.addWidget(self.alert_badge)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedHeight(20)
        sep.setStyleSheet(
            f"color: {self.config.COLORS['border']}; border: none; background: {self.config.COLORS['border']};"
        )
        layout.addWidget(sep)

        self.machine_count_label = QLabel("Devices: 0/0")
        self.machine_count_label.setStyleSheet(
            f"""
            color: {self.config.COLORS['text_muted']};
            font-size: 10px;
            background: transparent;
            border: none;
            """
        )
        layout.addWidget(self.machine_count_label)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFixedHeight(20)
        sep2.setStyleSheet(
            f"color: {self.config.COLORS['border']}; border: none; background: {self.config.COLORS['border']};"
        )
        layout.addWidget(sep2)

        self._fs_btn = QPushButton()
        self._fs_btn.setFixedSize(28, 24)
        self._fs_btn.setCursor(Qt.PointingHandCursor)
        self._fs_btn.setToolTip("Toggle Fullscreen  [F11]")
        c = self.config.COLORS
        ic = _icon("fa5s.expand", color=c["text_muted"])
        if ic:
            self._fs_btn.setIcon(ic)
        else:
            self._fs_btn.setText("[]")
        self._fs_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {c['border']};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {c['sidebar_item_hover']};
                border-color: {c['accent']};
            }}
            """
        )
        self._fs_btn.clicked.connect(self.fullscreen_requested)
        layout.addWidget(self._fs_btn)

    def _connect_signals(self):
        self.data_manager.alert_triggered.connect(self._on_alert)
        self.data_manager.devices_changed.connect(self._refresh_machine_count)
        self.data_manager.machine_status_changed.connect(lambda *_: self._refresh_machine_count())
        self.data_manager.data_updated.connect(lambda *_: self._refresh_machine_count())
        self._refresh_machine_count()

    def set_title(self, title: str):
        self.title_label.setText(title)

    def update_fullscreen_icon(self, is_fullscreen: bool):
        c = self.config.COLORS
        ic = _icon("fa5s.compress", color=c["accent"]) if is_fullscreen else _icon("fa5s.expand", color=c["text_muted"])
        if ic:
            self._fs_btn.setIcon(ic)

    @pyqtSlot(str, str, str)
    def _on_alert(self, _machine_id: str, level: str, _message: str):
        self._alert_count += 1
        color = "#ff9800" if level == "Warning" else "#f44336"
        suffix = "s" if self._alert_count > 1 else ""
        self.alert_badge.setText(f"* {self._alert_count} Alert{suffix}")
        self.alert_badge.setStyleSheet(
            f"""
            color: {color};
            font-size: 10px;
            background: transparent;
            border: none;
            """
        )

    def _refresh_machine_count(self):
        devices = self.data_manager.list_devices()
        total = len(devices)
        online = sum(1 for d in devices if d.get("status") != "Offline")
        color = self.config.COLORS["accent_success"] if online > 0 else self.config.COLORS["text_muted"]
        self.machine_count_label.setStyleSheet(
            f"color: {color}; font-size: 10px; background: transparent; border: none;"
        )
        self.machine_count_label.setText(f"Devices: {online}/{total}")
