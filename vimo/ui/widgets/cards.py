"""
Reusable UI widgets for the monitoring application.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from core.app_config import AppConfig


class StatCard(QWidget):
    """A metric display card with label, value, and optional unit/sub-label."""

    def __init__(self, title: str, value: str = "—", unit: str = "",
                 accent_color: str = None, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        accent = accent_color or self.config.COLORS["accent"]

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {self.config.COLORS['bg_card']};
                border-radius: {self.config.LAYOUT['card_radius']}px;
                border: 1px solid {self.config.COLORS['border']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Title
        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet(f"""
            color: {self.config.COLORS['text_muted']};
            font-size: 9px;
            letter-spacing: 1px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        layout.addWidget(title_lbl)

        # Value + unit row
        value_row = QHBoxLayout()
        value_row.setSpacing(4)
        value_row.setContentsMargins(0, 0, 0, 0)

        self.value_lbl = QLabel(value)
        self.value_lbl.setStyleSheet(f"""
            color: {self.config.COLORS['text_primary']};
            font-size: 22px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        value_row.addWidget(self.value_lbl)

        if unit:
            self.unit_lbl = QLabel(unit)
            self.unit_lbl.setStyleSheet(f"""
                color: {self.config.COLORS['text_secondary']};
                font-size: 11px;
                background: transparent;
                border: none;
                padding-top: 8px;
            """)
            value_row.addWidget(self.unit_lbl)

        value_row.addStretch()
        layout.addLayout(value_row)

        # Accent bottom bar
        bar = QFrame()
        bar.setFixedHeight(3)
        bar.setStyleSheet(f"background: {accent}; border: none; border-radius: 2px;")
        layout.addWidget(bar)

    def set_value(self, value: str):
        self.value_lbl.setText(value)


class MachineStatusCard(QWidget):
    """Compact status card for a single machine."""

    def __init__(self, machine_id: str, machine_name: str, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self.machine_id = machine_id

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {self.config.COLORS['bg_card']};
                border-radius: {self.config.LAYOUT['card_radius']}px;
                border: 1px solid {self.config.COLORS['border']};
            }}
            QWidget:hover {{
                border: 1px solid {self.config.COLORS['border_light']};
            }}
        """)
        self.setFixedHeight(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # Header row
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        self.name_lbl = QLabel(machine_name)
        self.name_lbl.setStyleSheet(f"""
            color: {self.config.COLORS['text_primary']};
            font-size: 12px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)

        self.status_lbl = QLabel("● Normal")
        self.status_lbl.setStyleSheet(f"""
            color: {self.config.COLORS['accent_success']};
            font-size: 10px;
            background: transparent;
            border: none;
        """)

        header_row.addWidget(self.name_lbl)
        header_row.addStretch()
        header_row.addWidget(self.status_lbl)
        layout.addLayout(header_row)

        # ID label
        id_lbl = QLabel(machine_id)
        id_lbl.setStyleSheet(f"""
            color: {self.config.COLORS['text_muted']};
            font-size: 9px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(id_lbl)

        # Value row
        self.readings_lbl = QLabel("Waiting for data...")
        self.readings_lbl.setStyleSheet(f"""
            color: {self.config.COLORS['text_secondary']};
            font-size: 10px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.readings_lbl)

    def update_reading(self, reading):
        status = reading.status
        status_colors = {
            "Normal": "#4caf50",
            "Warning": "#ff9800",
            "Critical": "#f44336",
        }
        color = status_colors.get(status, "#9e9e9e")
        self.status_lbl.setText(f"● {status}")
        self.status_lbl.setStyleSheet(f"""
            color: {color};
            font-size: 10px;
            background: transparent;
            border: none;
        """)
        self.readings_lbl.setText(
            f"Acc: ({reading.accel_x:.0f}, {reading.accel_y:.0f}, {reading.accel_z:.0f})  "
            f"Gyro: ({reading.gyro_x:.0f}, {reading.gyro_y:.0f}, {reading.gyro_z:.0f})"
        )


class SectionHeader(QWidget):
    """Section header with title and optional action button."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 4)

        self.lbl = QLabel(title)
        self.lbl.setStyleSheet(f"""
            color: {self.config.COLORS['text_secondary']};
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
            background: transparent;
        """)
        layout.addWidget(self.lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {self.config.COLORS['border']};")
        layout.addWidget(sep, 1)

    def setText(self, text: str):
        self.lbl.setText(text)
