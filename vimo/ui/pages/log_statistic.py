"""
Log & Statistics Page - System logs and statistical analysis.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QPushButton, QComboBox,
    QFrame, QSplitter, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer
from PyQt5.QtGui import QColor, QBrush, QFont

from core.app_config import AppConfig
from core.data_manager import DataManager
from ui.widgets.cards import SectionHeader, StatCard


class LogStatisticPage(QWidget):
    """Log viewer and statistical summary page."""

    LOG_COLUMNS = ["Time", "Level", "Source", "Message"]
    LOG_COLORS = {
        "INFO":     "#4a9eff",
        "WARN":     "#ff9800",
        "CRITICAL": "#f44336",
        "ERROR":    "#f44336",
    }

    def __init__(self, data_manager: DataManager, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self.data_manager = data_manager
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)

        # Title
        title = QLabel("Log & Statistics")
        title.setStyleSheet(f"""
            color: {self.config.COLORS['text_primary']};
            font-size: 18px;
            font-weight: bold;
        """)
        layout.addWidget(title)
        subtitle = QLabel("System event log and sensor data statistics")
        subtitle.setStyleSheet(f"color: {self.config.COLORS['text_muted']}; font-size: 10px;")
        layout.addWidget(subtitle)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self._stat_info = StatCard("INFO Events", "0", "", self.config.COLORS["accent_info"])
        self._stat_warn = StatCard("Warnings", "0", "", self.config.COLORS["accent_warning"])
        self._stat_crit = StatCard("Critical", "0", "", self.config.COLORS["accent_danger"])
        self._stat_total = StatCard("Total Logs", "0", "", self.config.COLORS["accent"])
        stats_row.addWidget(self._stat_info)
        stats_row.addWidget(self._stat_warn)
        stats_row.addWidget(self._stat_crit)
        stats_row.addWidget(self._stat_total)
        layout.addLayout(stats_row)

        # Controls row
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Levels", "INFO", "WARN", "CRITICAL", "ERROR"])
        self.filter_combo.setFixedHeight(28)
        self.filter_combo.setStyleSheet(self._combo_style())
        self.filter_combo.currentTextChanged.connect(self._apply_filter)

        clear_btn = QPushButton("Clear Logs")
        clear_btn.setFixedHeight(28)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(self._btn_style())
        clear_btn.clicked.connect(self._clear_logs)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedHeight(28)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(self._btn_style())
        refresh_btn.clicked.connect(self._reload_logs)

        ctrl_row.addWidget(QLabel("Filter:"))
        ctrl_row.addWidget(self.filter_combo)
        ctrl_row.addStretch()
        ctrl_row.addWidget(refresh_btn)
        ctrl_row.addWidget(clear_btn)
        layout.addLayout(ctrl_row)

        # Log table
        layout.addWidget(SectionHeader("SYSTEM LOGS"))
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(len(self.LOG_COLUMNS))
        self.log_table.setHorizontalHeaderLabels(self.LOG_COLUMNS)
        self.log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.log_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setSortingEnabled(False)

        header = self.log_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        c = self.config.COLORS
        self.log_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: {self.config.LAYOUT['card_radius']}px;
                gridline-color: {c['border']};
                font-size: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
            }}
            QTableWidget::item {{ padding: 3px 8px; }}
            QTableWidget::item:selected {{
                background-color: {c['sidebar_item_active']};
            }}
            QHeaderView::section {{
                background-color: {c['bg_secondary']};
                color: {c['text_secondary']};
                border: none;
                border-bottom: 1px solid {c['border']};
                padding: 4px 8px;
                font-size: 9px;
                font-weight: bold;
            }}
        """)
        self.log_table.setMinimumHeight(300)
        layout.addWidget(self.log_table, 1)

        # Stats summary
        layout.addWidget(SectionHeader("SENSOR STATISTICS"))
        self.stats_label = QLabel("Waiting for data...")
        self.stats_label.setStyleSheet(f"""
            color: {self.config.COLORS['text_secondary']};
            font-size: 10px;
            background: {self.config.COLORS['bg_card']};
            border: 1px solid {self.config.COLORS['border']};
            border-radius: {self.config.LAYOUT['card_radius']}px;
            padding: 12px;
        """)
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)

        # Stats refresh
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._update_stats)
        self._stats_timer.start(5000)

        self._counts = {"INFO": 0, "WARN": 0, "CRITICAL": 0, "ERROR": 0}
        self._current_filter = "All Levels"

    def _connect_signals(self):
        self.data_manager.log_entry_added.connect(self._on_log_entry)

    @pyqtSlot(dict)
    def _on_log_entry(self, entry: dict):
        level = entry.get("level", "INFO")
        if level in self._counts:
            self._counts[level] += 1

        # Update counters
        self._stat_info.set_value(str(self._counts["INFO"]))
        self._stat_warn.set_value(str(self._counts["WARN"]))
        self._stat_crit.set_value(str(self._counts.get("CRITICAL", 0)))
        total = sum(self._counts.values())
        self._stat_total.set_value(str(total))

        # Apply filter
        if self._current_filter != "All Levels" and level != self._current_filter:
            return

        self._add_table_row(entry)

    def _add_table_row(self, entry: dict):
        row = 0
        self.log_table.insertRow(row)
        level = entry.get("level", "INFO")
        color = self.LOG_COLORS.get(level, "#9e9e9e")

        values = [
            entry["timestamp"].strftime("%H:%M:%S"),
            level,
            entry.get("source", "—"),
            entry.get("message", ""),
        ]

        for col, val in enumerate(values):
            item = QTableWidgetItem(val)
            if col == 1:  # level column
                item.setForeground(QBrush(QColor(color)))
            self.log_table.setItem(row, col, item)

        if self.log_table.rowCount() > 500:
            self.log_table.removeRow(self.log_table.rowCount() - 1)

    def _apply_filter(self, filter_text: str):
        self._current_filter = filter_text
        self._reload_logs()

    def _reload_logs(self):
        self.log_table.setRowCount(0)
        logs = self.data_manager.get_logs(limit=300)
        for entry in reversed(logs):
            level = entry.get("level", "INFO")
            if self._current_filter != "All Levels" and level != self._current_filter:
                continue
            self._add_table_row(entry)

    def _clear_logs(self):
        self.log_table.setRowCount(0)

    def _update_stats(self):
        """Compute and display sensor statistics."""
        machines = self.data_manager.get_all_machines()
        lines = []
        for machine in machines:
            buf = self.data_manager.get_buffer(machine.machine_id)
            if not buf or len(buf) == 0:
                continue
            readings = buf.get_all()
            if not readings:
                continue

            accel_mags = [r.accel_magnitude for r in readings]
            gyro_mags = [r.gyro_magnitude for r in readings]
            n = len(readings)

            accel_avg = sum(accel_mags) / n
            accel_max = max(accel_mags)
            gyro_avg = sum(gyro_mags) / n
            gyro_max = max(gyro_mags)

            lines.append(
                f"{machine.name} ({machine.machine_id})  |  "
                f"Readings: {n}  |  "
                f"Accel Mag: avg={accel_avg:.0f}, max={accel_max:.0f}  |  "
                f"Gyro Mag: avg={gyro_avg:.0f}, max={gyro_max:.0f}  |  "
                f"Status: {machine.status}"
            )

        self.stats_label.setText("\n".join(lines) if lines else "Waiting for data...")

    def _combo_style(self):
        c = self.config.COLORS
        return f"""
            QComboBox {{
                background: {c['bg_secondary']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 0 8px;
                font-size: 10px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {c['bg_secondary']};
                color: {c['text_primary']};
                selection-background-color: {c['accent']};
            }}
        """

    def _btn_style(self):
        c = self.config.COLORS
        return f"""
            QPushButton {{
                background: {c['bg_secondary']};
                color: {c['text_secondary']};
                border: 1px solid {c['border']};
                border-radius: 3px;
                padding: 0 12px;
                font-size: 10px;
            }}
            QPushButton:hover {{ background: {c['bg_card']}; color: {c['text_primary']}; }}
        """
