"""
Activity Page - Shows real-time machine activity feed and alerts.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QListWidget, QListWidgetItem,
    QTextEdit, QPushButton, QSplitter, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer
from PyQt5.QtGui import QColor, QBrush, QFont

from core.app_config import AppConfig
from core.data_manager import DataManager
from ui.widgets.cards import SectionHeader, StatCard
from ui.widgets.charts import RealtimeChart


class ActivityPage(QWidget):
    """Activity page with alert feed and per-machine live charts."""

    def __init__(self, data_manager: DataManager, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self.data_manager = data_manager
        self._primary_machine_id = self._resolve_primary_machine_id()
        self._alert_count = 0
        self._build_ui()
        self._connect_signals()

        self._chart_timer = QTimer(self)
        self._chart_timer.timeout.connect(self._refresh_chart)
        self._chart_timer.start(100)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)

        # Title and Machine Selector Row
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        
        title_box = QVBoxLayout()
        title = QLabel("Activity Monitor")
        title.setStyleSheet(f"""
            color: {self.config.COLORS['text_primary']};
            font-size: 18px;
            font-weight: bold;
        """)
        title_box.addWidget(title)

        subtitle = QLabel("Live machine activity, events, and alert history")
        subtitle.setStyleSheet(f"color: {self.config.COLORS['text_muted']}; font-size: 10px;")
        title_box.addWidget(subtitle)
        
        header_row.addLayout(title_box)
        header_row.addStretch()
        
        # Machine Selector Dropdown
        self.machine_selector = QComboBox()
        self.machine_selector.setFixedWidth(200)
        self.machine_selector.setFixedHeight(30)
        self.machine_selector.setCursor(Qt.PointingHandCursor)
        self.machine_selector.setStyleSheet(f"""
            QComboBox {{
                background: {self.config.COLORS['bg_secondary']};
                color: {self.config.COLORS['text_primary']};
                border: 1px solid {self.config.COLORS['border']};
                border-radius: 4px;
                padding: 0 10px;
                font-size: 11px;
            }}
            QComboBox::drop-down {{ border: none; }}
        """)
        self.machine_selector.currentIndexChanged.connect(self._on_machine_selected)
        header_row.addWidget(self.machine_selector)
        
        layout.addLayout(header_row)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self._alerts_card = StatCard("Total Alerts", "0", "", self.config.COLORS["accent_danger"])
        self._events_card = StatCard("Events Today", "0", "", self.config.COLORS["accent_warning"])
        self._uptime_card = StatCard("System Uptime", "0", "min", self.config.COLORS["accent_success"])
        stats_row.addWidget(self._alerts_card)
        stats_row.addWidget(self._events_card)
        stats_row.addWidget(self._uptime_card)
        stats_row.addStretch()
        layout.addLayout(stats_row)

        # Main split: chart + alert feed
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {self.config.COLORS['border']}; }}")

        # Left: gyro magnitude chart
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        self._gyro_header = SectionHeader(f"GYROSCOPE MAGNITUDE ({self._primary_machine_id})")
        left_layout.addWidget(self._gyro_header)

        self.gyro_chart = RealtimeChart(
            title="Gyro Magnitude — Real Time (raw vs filtered)",
            y_label="Magnitude",
            max_points=150
        )
        self.gyro_chart.add_series("gyro_mag",   self.config.COLORS["border"],       label="Raw")
        self.gyro_chart.add_series("gyro_mag_f", self.config.COLORS["accent"],       label="Filtered")
        self.gyro_chart.setMinimumHeight(250)
        left_layout.addWidget(self.gyro_chart)

        # Accel magnitude
        self._accel_header = SectionHeader(f"ACCELERATION MAGNITUDE ({self._primary_machine_id})")
        left_layout.addWidget(self._accel_header)
        self.accel_chart = RealtimeChart(
            title="Accel Magnitude — Real Time (raw vs filtered)",
            y_label="Magnitude",
            max_points=150
        )
        self.accel_chart.add_series("accel_mag",   self.config.COLORS["border"],          label="Raw")
        self.accel_chart.add_series("accel_mag_f", self.config.COLORS["accent_success"],  label="Filtered")
        self.accel_chart.setMinimumHeight(220)
        left_layout.addWidget(self.accel_chart)
        left_layout.addStretch()

        splitter.addWidget(left_widget)

        # Right: alert feed
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(6)
        right_layout.addWidget(SectionHeader("ALERT FEED"))

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(24)
        clear_btn.setFixedWidth(60)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.config.COLORS['bg_secondary']};
                color: {self.config.COLORS['text_secondary']};
                border: 1px solid {self.config.COLORS['border']};
                border-radius: 3px;
                font-size: 10px;
            }}
            QPushButton:hover {{ background: {self.config.COLORS['bg_card']}; }}
        """)
        clear_btn.clicked.connect(self._clear_alerts)
        right_layout.addWidget(clear_btn, 0, Qt.AlignRight)

        self.alert_list = QListWidget()
        self.alert_list.setStyleSheet(f"""
            QListWidget {{
                background: {self.config.COLORS['bg_card']};
                border: 1px solid {self.config.COLORS['border']};
                border-radius: {self.config.LAYOUT['card_radius']}px;
                color: {self.config.COLORS['text_primary']};
                font-size: 10px;
            }}
            QListWidget::item {{
                padding: 6px 10px;
                border-bottom: 1px solid {self.config.COLORS['border']};
            }}
            QListWidget::item:selected {{
                background: {self.config.COLORS['sidebar_item_active']};
            }}
        """)
        right_layout.addWidget(self.alert_list)
        splitter.addWidget(right_widget)

        splitter.setSizes([700, 350])
        layout.addWidget(splitter, 1)

        # Uptime timer
        self._start_time = None
        self._uptime_timer = QTimer(self)
        self._uptime_timer.timeout.connect(self._update_uptime)
        self._uptime_timer.start(30000)  # every 30s

    def _connect_signals(self):
        self.data_manager.data_updated.connect(self._on_data_updated)
        self.data_manager.alert_triggered.connect(self._on_alert)
        self.data_manager.connection_status_changed.connect(self._on_connection)
        self.data_manager.devices_changed.connect(self._on_devices_changed)
        self._events_total = 0
        # Fill initial selector options
        self._update_machine_selector()

    @pyqtSlot(bool)
    def _on_connection(self, connected: bool):
        if connected:
            from datetime import datetime
            self._start_time = datetime.now()

    @pyqtSlot(str, object)
    def _on_data_updated(self, machine_id: str, reading):
        if machine_id == self._primary_machine_id:
            # Tampilkan raw dan filtered magnitude di activity
            self.gyro_chart.push("gyro_mag",    reading.gyro_magnitude,   reading.timestamp)
            self.gyro_chart.push("gyro_mag_f",  reading.gyro_magnitude_f, reading.timestamp)
            self.accel_chart.push("accel_mag",   reading.accel_magnitude,  reading.timestamp)
            self.accel_chart.push("accel_mag_f", reading.accel_magnitude_f, reading.timestamp)
        self._events_total += 1
        self._events_card.set_value(f"{self._events_total:,}")

    @pyqtSlot(str, str, str)
    def _on_alert(self, machine_id: str, level: str, message: str):
        from datetime import datetime
        self._alert_count += 1
        self._alerts_card.set_value(str(self._alert_count))

        color_map = {"Warning": "#ff9800", "Critical": "#f44336"}
        color = color_map.get(level, "#9e9e9e")

        item = QListWidgetItem(
            f"[{datetime.now().strftime('%H:%M:%S')}] {level}: {machine_id}\n  {message}"
        )
        item.setForeground(QBrush(QColor(color)))
        self.alert_list.insertItem(0, item)

        if self.alert_list.count() > 200:
            self.alert_list.takeItem(self.alert_list.count() - 1)

    def _clear_alerts(self):
        self.alert_list.clear()
        self._alert_count = 0
        self._alerts_card.set_value("0")

    def _update_uptime(self):
        if self._start_time:
            from datetime import datetime
            mins = int((datetime.now() - self._start_time).total_seconds() / 60)
            self._uptime_card.set_value(str(mins))

    def _refresh_chart(self):
        self.gyro_chart.refresh()
        self.accel_chart.refresh()

    def _resolve_primary_machine_id(self) -> str:
        machines = self.data_manager.get_all_machines()
        return machines[0].machine_id if machines else "N/A"

    def _update_machine_selector(self):
        self.machine_selector.blockSignals(True)
        self.machine_selector.clear()
        
        machines = self.data_manager.get_all_machines()
        if not machines:
            self.machine_selector.addItem("No Devices Available", "N/A")
        else:
            for m in machines:
                self.machine_selector.addItem(f"{m.name} ({m.machine_id})", m.machine_id)
                
            # Restoring selection if possible
            idx = self.machine_selector.findData(self._primary_machine_id)
            if idx >= 0:
                self.machine_selector.setCurrentIndex(idx)
            else:
                self.machine_selector.setCurrentIndex(0)
                self._primary_machine_id = self.machine_selector.itemData(0)
                
        self.machine_selector.blockSignals(False)

    def _on_machine_selected(self, index):
        if index >= 0:
            machine_id = self.machine_selector.itemData(index)
            if machine_id != self._primary_machine_id:
                self._primary_machine_id = machine_id
                # Update headers
                self._gyro_header.setText(f"GYROSCOPE MAGNITUDE ({machine_id})")
                self._accel_header.setText(f"ACCELERATION MAGNITUDE ({machine_id})")
                
                # Clear charts so old device data isn't lingering
                for chart in [self.gyro_chart, self.accel_chart]:
                    for series in chart._series.values():
                        series.clear()
                    chart._dirty = True
                    chart.refresh()
                    

    def _on_devices_changed(self):
        self._update_machine_selector()
        
        # If the currently selected machine was deleted, fallback to the first one
        if not self.data_manager.get_machine(self._primary_machine_id):
            self._primary_machine_id = self._resolve_primary_machine_id()
            self._update_machine_selector()
