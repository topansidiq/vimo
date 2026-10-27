"""
Dashboard Page - Overview monitoring semua mesin dengan real-time charts.

Optimasi performa:
- Chart refresh dari 100ms → 250ms (4 fps cukup untuk monitoring)
- DualModeChart menampilkan raw + filtered sekaligus
- Semua chart hanya refresh jika dirty flag aktif
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QScrollArea, QFrame, QTabWidget, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer

from core.app_config import AppConfig
from core.data_manager import DataManager
from ui.widgets.cards import StatCard, MachineStatusCard, SectionHeader
from ui.widgets.charts import DualModeChart, TrajectoryChart, ScatterPlotChart
from ui.widgets.data_table import LiveDataTable

import qtawesome as qta
import xlsxwriter
import os
import logging
from datetime import datetime

LOGGER = logging.getLogger(__name__)


class DashboardPage(QWidget):
    """Dashboard utama — overview semua mesin dan data real-time."""

    def _icon(self, name: str, **kwargs):
        """Return a QIcon from Font Awesome via qtawesome."""
        try:
            # Menggunakan text_secondary sebagai default jika color tidak diberikan
            if 'color' not in kwargs:
                kwargs['color'] = self.config.COLORS["text_secondary"]
            return qta.icon(name, **kwargs)
        except Exception:
            return None

    def __init__(self, data_manager: DataManager, parent=None):
        super().__init__(parent)
        self.config       = AppConfig()
        self.data_manager = data_manager

        self._stat_cards:    dict = {}
        self._machine_cards: dict = {}
        self._charts:        dict = {}   # machine_id -> (accel_chart, gyro_chart, traj_chart, scat_chart)
        self._readings_total = 0
        self._alert_count    = 0
        self._rate_count     = 0

        self._build_ui()
        self._rebuild_machines_ui()
        self._connect_signals()

        # Chart refresh 250ms (4 Hz) — cukup untuk monitoring, jauh lebih ringan
        self._chart_timer = QTimer(self)
        self._chart_timer.timeout.connect(self._refresh_charts)
        self._chart_timer.start(250)

        # Data rate counter
        self._rate_timer = QTimer(self)
        self._rate_timer.timeout.connect(self._update_rate)
        self._rate_timer.start(1000)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        main_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(14)

        # ── Judul ────────────────────────────────────────────────────────────
        title = QLabel("Dashboard")
        title.setStyleSheet(f"color:{self.config.COLORS['text_primary']};"
                            "font-size:18px;font-weight:bold;background:transparent;")
        layout.addWidget(title)

        subtitle = QLabel("Real-time monitoring")
        subtitle.setStyleSheet(f"color:{self.config.COLORS['text_muted']};"
                               "font-size:10px;background:transparent;")
        layout.addWidget(subtitle)

        # ── Stat Cards ───────────────────────────────────────────────────────
        layout.addWidget(SectionHeader("OVERVIEW"))
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        total_machines = len(self.data_manager.get_all_machines())
        online_machines = sum(1 for m in self.data_manager.get_all_machines() if m.status != "Offline")

        for key, title_text, value, unit, color in [
            ("total_readings",  "Total Readings",   "0",   "",    self.config.COLORS["accent"]),
            ("machines_online", "Devices Online",   str(online_machines), f"/ {total_machines}", self.config.COLORS["accent_success"]),
            ("active_alerts",   "Active Alerts",    "0",   "",    self.config.COLORS["accent_danger"]),
            ("data_rate",       "UI Update Rate",   "0",   "Hz",  self.config.COLORS["accent_info"]),
        ]:
            card = StatCard(title_text, value, unit, accent_color=color)
            self._stat_cards[key] = card
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        layout.addWidget(SectionHeader("MAINTENANCE INSIGHTS"))
        self._maintenance_label = QLabel("")
        self._maintenance_label.setWordWrap(True)
        self._maintenance_label.setStyleSheet(
            f"color: {self.config.COLORS['text_secondary']}; font-size: 11px; background: transparent;"
        )
        layout.addWidget(self._maintenance_label)

        # ── Machine Status Cards (Container) ──────────────────────────────────
        layout.addWidget(SectionHeader("MACHINE STATUS"))
        self._machines_container = QWidget()
        self._machines_layout = QHBoxLayout(self._machines_container)
        self._machines_layout.setContentsMargins(0, 0, 0, 0)
        self._machines_layout.setSpacing(12)
        layout.addWidget(self._machines_container)

        # ── Charts per mesin (Container) ─────────────────────────────────────
        layout.addWidget(SectionHeader("REAL-TIME SENSOR DATA (RAW + FILTERED)"))

        self._chart_tabs = QTabWidget()
        self._chart_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background: {self.config.COLORS['bg_card']};
                border: 1px solid {self.config.COLORS['border']};
                border-radius: {self.config.LAYOUT['card_radius']}px;
            }}
            QTabBar::tab {{
                background: {self.config.COLORS['bg_secondary']};
                color: {self.config.COLORS['text_secondary']};
                padding: 5px 14px;
                border: 1px solid {self.config.COLORS['border']};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 10px;
            }}
            QTabBar::tab:selected {{
                background: {self.config.COLORS['bg_card']};
                color: {self.config.COLORS['text_primary']};
                border-bottom: 2px solid {self.config.COLORS['accent']};
            }}
        """)
        from PyQt5.QtWidgets import QSizePolicy
        self._chart_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._chart_tabs.setMinimumHeight(450)
        layout.addWidget(self._chart_tabs, stretch=1)

        # ── Export Actions ───────────────────────────────────────────────────
        layout.addWidget(SectionHeader("EXPORT & REPORTS"))
        export_row = QHBoxLayout()
        export_row.setSpacing(10)

        # 1. Initialize Buttons
        self.btn_excel = QPushButton("  Export Excel")
        self.btn_pdf   = QPushButton("  Export PDF")
        self.btn_cap   = QPushButton("  Capture View")

        # 2. Appearance & Style
        btn_style = f"""
            QPushButton {{
                background: {self.config.COLORS['bg_secondary']};
                color: {self.config.COLORS['text_primary']};
                border: 1px solid {self.config.COLORS['border']};
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {self.config.COLORS['bg_card_hover']};
                border-color: {self.config.COLORS['accent']};
            }}
        """

        muted_color = self.config.COLORS["text_muted"]
        
        # 3. Setup Buttons (Icons & Style)
        for btn, icon_name in [
            (self.btn_excel, "fa5s.file-excel"),
            (self.btn_pdf,   "fa5s.file-pdf"),
            (self.btn_cap,   "fa5s.camera")
        ]:
            ic = self._icon(icon_name, color=muted_color)
            if ic:
                btn.setIcon(ic)
            
            btn.setStyleSheet(btn_style)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)
            export_row.addWidget(btn)

        # 4. Connect Signals
        self.btn_excel.clicked.connect(self._export_excel)
        self.btn_pdf.clicked.connect(self._export_pdf)
        self.btn_cap.clicked.connect(self._screen_capture)

        export_row.addStretch()
        layout.addLayout(export_row)

        # ── Live Table ────────────────────────────────────────────────────────
        layout.addWidget(SectionHeader("LATEST READINGS (RAW vs FILTERED)"))
        self.live_table = LiveDataTable()
        self.live_table.setFixedHeight(200)
        layout.addWidget(self.live_table)

        layout.addStretch()

    def _connect_signals(self):
        self.data_manager.data_updated.connect(self._on_data_updated)
        self.data_manager.devices_changed.connect(self._rebuild_machines_ui)
        self.data_manager.alert_triggered.connect(self._on_alert)
        self.data_manager.machine_status_changed.connect(self._on_machine_status_for_dashboard)
        self.data_manager.devices_changed.connect(self._update_machine_online_stat)

    @pyqtSlot()
    def _on_machine_status_for_dashboard(self):
        self._update_machine_online_stat()
        self._update_maintenance_panel()

    def _update_maintenance_panel(self):
        insights = self.data_manager.get_maintenance_insights()
        if not insights:
            self._maintenance_label.setText("There are currently no priority maintenance signals.")
            return
        lines = []
        for ins in insights:
            pr = str(ins.get("priority", "")).upper()
            name = ins.get("name") or ins.get("machine_id", "")
            lines.append(f"[{pr}] {name}: {ins.get('summary', '')}")
        self._maintenance_label.setText("\n".join(lines))

    def _rebuild_machines_ui(self):
        """Rebuild machine cards and chart tabs when devices are added/removed."""
        # Clean up existing status cards
        while self._machines_layout.count():
            item = self._machines_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._machine_cards.clear()

        # Clean up chart tabs
        self._chart_tabs.clear()
        self._charts.clear()

        # Re-build for current machines
        machines = self.data_manager.get_all_machines()
        for machine in machines:
            # 1. Status Card
            card = MachineStatusCard(machine.machine_id, machine.name)
            self._machine_cards[machine.machine_id] = card
            self._machines_layout.addWidget(card)

            # 2. Chart Tab
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(8, 8, 8, 8)
            tab_layout.setSpacing(8)

            # Machine Tab Header (Title + Calibrate Button)
            head_row = QHBoxLayout()
            head_row.setContentsMargins(0, 0, 0, 4)
            m_title = QLabel(f"<b style='color: {self.config.COLORS['accent']}'>{machine.name} Dashboard</b>")
            m_title.setStyleSheet("font-size: 11px;")
            
            zero_btn = QPushButton("⟳ Zero Sensors")
            zero_btn.setFixedSize(90, 20)
            zero_btn.setCursor(Qt.PointingHandCursor)
            zero_btn.setToolTip(f"Calibrate {machine.name} to its current position")
            zero_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {self.config.COLORS['bg_secondary']};
                    color: {self.config.COLORS['text_muted']};
                    border: 1px solid {self.config.COLORS['border']};
                    border-radius: 4px; font-size: 9px; font-weight: bold;
                }}
                QPushButton:hover {{ background: {self.config.COLORS['accent']}; color: white; }}
            """)
            zero_btn.clicked.connect(lambda checked, mid=machine.machine_id: self.data_manager.calibrate(mid))
            
            head_row.addWidget(m_title)
            head_row.addStretch()
            head_row.addWidget(zero_btn)
            tab_layout.addLayout(head_row)

            # Inner tab widget for different views per machine
            machine_tabs = QTabWidget()
            machine_tabs.setStyleSheet("QTabWidget::pane { border: none; }")

            # View 1: Time Series
            ts_view = QWidget()
            ts_layout = QHBoxLayout(ts_view)
            ts_layout.setContentsMargins(0, 0, 0, 0)
            accel_chart = DualModeChart(mode="accel", machine_name=machine.name)
            gyro_chart  = DualModeChart(mode="gyro",  machine_name=machine.name)
            ts_layout.addWidget(accel_chart)
            ts_layout.addWidget(gyro_chart)
            machine_tabs.addTab(ts_view, "Real-time Series")

            # View 2: Advanced Analytics
            ana_view = QWidget()
            ana_layout = QHBoxLayout(ana_view)
            ana_layout.setContentsMargins(0, 0, 0, 0)
            traj_chart = TrajectoryChart(machine_name=machine.name)
            scat_chart = ScatterPlotChart(machine_name=machine.name)
            ana_layout.addWidget(traj_chart)
            ana_layout.addWidget(scat_chart)
            machine_tabs.addTab(ana_view, "Advanced Analytics")

            tab_layout.addWidget(machine_tabs)
            self._chart_tabs.addTab(tab, machine.name)
            self._charts[machine.machine_id] = (accel_chart, gyro_chart, traj_chart, scat_chart)

        self._machines_layout.addStretch()
        self._update_machine_online_stat()

    @pyqtSlot(str, object)
    def _on_data_updated(self, machine_id: str, reading):
        self._readings_total += 1
        self._rate_count     += 1

        # Update machine status card
        if machine_id in self._machine_cards:
            self._machine_cards[machine_id].update_reading(reading)

        # Push ke semua chart (hanya set data, belum render)
        if machine_id in self._charts:
            for chart in self._charts[machine_id]:
                chart.update_reading(reading)

        # Buffer ke tabel (belum render ke UI)
        self.live_table.add_row(machine_id, reading)

        self._stat_cards["total_readings"].set_value(f"{self._readings_total:,}")
        self._update_machine_online_stat()

    @pyqtSlot(str, str, str)
    def _on_alert(self, machine_id: str, level: str, message: str):
        self._alert_count += 1
        self._stat_cards["active_alerts"].set_value(str(self._alert_count))

    def _update_rate(self):
        self._stat_cards["data_rate"].set_value(str(self._rate_count))
        self._rate_count = 0

    def _update_machine_online_stat(self):
        total = len(self.data_manager.get_all_machines())
        online = sum(1 for m in self.data_manager.get_all_machines() if m.status != "Offline")
        card = self._stat_cards.get("machines_online")
        if card:
            card.set_value(str(online))
            if hasattr(card, "unit_lbl"):
                card.unit_lbl.setText(f"/ {total}")

    def _refresh_charts(self):
        """
        Render ulang chart — hanya aktif jika ada data baru (dirty flag)
        DAN jika chart sedang terlihat (isVisible) untuk optimasi performa.
        """
        self._update_maintenance_panel()
        for charts in self._charts.values():
            for chart in charts:
                # OPTIMASI: Lewati redraw Matplotlib yang mahal jika widget tidak terlihat
                # Ini akan menghemat banyak CPU saat user berada di tab mesin lain.
                if chart.isVisible():
                    chart.refresh()

    def _export_excel(self):
        filename = f"Vimo_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        try:
            workbook = xlsxwriter.Workbook(filename)
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
            
            for machine in self.data_manager.get_all_machines():
                sheet = workbook.add_worksheet(machine.name[:31])
                headers = ["Timestamp", "Accel X", "Accel Y", "Accel Z", "Gyro X", "Gyro Y", "Gyro Z", 
                           "Accel X (F)", "Accel Y (F)", "Accel Z (F)", "Gyro X (F)", "Gyro Y (F)", "Gyro Z (F)"]
                
                for col, h in enumerate(headers):
                    sheet.set_column(col, col, 15)
                    sheet.write(0, col, h, header_fmt)
                
                buffer = self.data_manager.get_buffer(machine.machine_id)
                if buffer:
                    readings = buffer.get_all()
                    for row, r in enumerate(readings, 1):
                        sheet.write(row, 0, r.timestamp.strftime("%H:%M:%S.%f")[:-3])
                        sheet.write(row, 1, r.accel_x)
                        sheet.write(row, 2, r.accel_y)
                        sheet.write(row, 3, r.accel_z)
                        sheet.write(row, 4, r.gyro_x)
                        sheet.write(row, 5, r.gyro_y)
                        sheet.write(row, 6, r.gyro_z)
                        sheet.write(row, 7, r.accel_x_f if r.accel_x_f is not None else r.accel_x)
                        sheet.write(row, 8, r.accel_y_f if r.accel_y_f is not None else r.accel_y)
                        sheet.write(row, 9, r.accel_z_f if r.accel_z_f is not None else r.accel_z)
                        sheet.write(row, 10, r.gyro_x_f if r.gyro_x_f is not None else r.gyro_x)
                        sheet.write(row, 11, r.gyro_y_f if r.gyro_y_f is not None else r.gyro_y)
                        sheet.write(row, 12, r.gyro_z_f if r.gyro_z_f is not None else r.gyro_z)
            
            workbook.close()
            LOGGER.info("Excel exported to %s", filename)
            QMessageBox.information(self, "Export Excel", f"Successfully exported Excel:\n{filename}")
        except Exception as e:
            LOGGER.exception("Excel export failed: %s", e)
            QMessageBox.warning(self, "Export Excel", f"Failed to export Excel:\n{e}")

    def _export_pdf(self):
        """Export charts to PDF using matplotlib's PdfPages."""
        from matplotlib.backends.backend_pdf import PdfPages
        filename = f"Vimo_Charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        try:
            with PdfPages(filename) as pdf:
                for machine_id, charts in self._charts.items():
                    # machines name
                    machine = self.data_manager.get_machine(machine_id)
                    mname = machine.name if machine else machine_id
                    
                    for i, chart in enumerate(charts):
                        # Add metadata or title to the figure temporarily if needed
                        pdf.savefig(chart.figure)
            LOGGER.info("PDF exported to %s", filename)
            QMessageBox.information(self, "Export PDF", f"Successfully exported PDF:\n{filename}")
        except Exception as e:
            LOGGER.exception("PDF export failed: %s", e)
            QMessageBox.warning(self, "Export PDF", f"Failed to export PDF:\n{e}")

    def _screen_capture(self):
        filename = f"Vimo_Screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        try:
            pixmap = self.grab()
            pixmap.save(filename)
            LOGGER.info("Screenshot saved to %s", filename)
            QMessageBox.information(self, "Capture View", f"Screenshot saved:\n{filename}")
        except Exception as e:
            LOGGER.exception("Screenshot failed: %s", e)
            QMessageBox.warning(self, "Capture View", f"Failed to save screenshot:\n{e}")
