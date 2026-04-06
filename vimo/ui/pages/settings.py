"""
Settings Page - Application and connection configuration.
Loads from / saves to runtime root `connection.json` via connection_config module.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QSpinBox,
    QGroupBox, QFormLayout, QComboBox, QFrame,
    QScrollArea, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer
import qtawesome as qta

from core.app_config import AppConfig
from core.data_manager import DataManager
from core import connection_config
from ui.widgets.cards import SectionHeader


def _icon(name, color="#9e9e9e"):
    try:
        return qta.icon(name, color=color)
    except Exception:
        return None


class SettingsPage(QWidget):
    """Application settings and configuration page."""

    def __init__(self, data_manager: DataManager, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self.data_manager = data_manager
        self._build_ui()
        self._load_saved_config()

    # ─────────────────────────────────────────────────────────────────────────
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
        layout.setSpacing(16)

        # Title
        title = QLabel("Settings")
        title.setStyleSheet(f"color: {self.config.COLORS['text_primary']}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        subtitle = QLabel(
            "Server connection, transport (HTTP / MQTT / WebSocket), alert thresholds, and display preferences"
        )
        subtitle.setStyleSheet(f"color: {self.config.COLORS['text_muted']}; font-size: 10px;")
        layout.addWidget(subtitle)

        # ── Connection ────────────────────────────────────────────────────────
        layout.addWidget(SectionHeader("SERVER CONNECTION"))
        conn_group = self._make_group()
        conn_form = QFormLayout(conn_group)
        conn_form.setSpacing(10)
        conn_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.host_input = self._make_input("192.168.1.2",
            tooltip="IP address or hostname of your bridge server")
        self.port_input = self._make_input("5000",
            tooltip="Port of the Flask-SocketIO bridge (default: 5000)")
        self.port_input.setFixedWidth(120)

        conn_form.addRow("Bridge Server Host:", self.host_input)
        conn_form.addRow("Bridge Server Port:", self.port_input)

        self.transport_combo = QComboBox()
        self.transport_combo.setFixedHeight(30)
        for text, key in (
            ("WebSocket (Socket.IO)", "websocket"),
            ("MQTT (broker langsung)", "mqtt"),
            ("HTTP (sinkron perangkat saja)", "http"),
            ("Modbus TCP (rencana)", "modbus"),
        ):
            self.transport_combo.addItem(text, key)
        c = self.config.COLORS
        self.transport_combo.setStyleSheet(f"""
            QComboBox {{
                background: {c['bg_secondary']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 4px;
                padding: 0 8px;
                font-size: 11px;
                min-width: 220px;
            }}
            QComboBox::drop-down {{ border: none; }}
        """)
        self.transport_combo.currentIndexChanged.connect(self._on_transport_changed)
        conn_form.addRow("Transport data:", self.transport_combo)

        self._mqtt_container = QWidget()
        mqtt_form = QFormLayout(self._mqtt_container)
        mqtt_form.setSpacing(10)
        mqtt_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.mqtt_host_input = self._make_input("127.0.0.1", tooltip="Host broker MQTT (mis. Mosquitto lokal)")
        self.mqtt_port_input = self._make_input("1883", tooltip="Port broker (biasanya 1883)")
        self.mqtt_port_input.setFixedWidth(120)
        self.mqtt_pattern_input = self._make_input(
            "vimo/devices/+/data",
            tooltip="Wildcard subscribe; harus cocok dengan topik perangkat Anda",
        )
        mqtt_form.addRow("MQTT broker host:", self.mqtt_host_input)
        mqtt_form.addRow("MQTT broker port:", self.mqtt_port_input)
        mqtt_form.addRow("Subscribe pattern:", self.mqtt_pattern_input)
        conn_form.addRow(self._mqtt_container)

        self._transport_hint = QLabel("")
        self._transport_hint.setWordWrap(True)
        self._transport_hint.setStyleSheet(
            f"color: {self.config.COLORS['text_muted']}; font-size: 10px; background: transparent;")
        conn_form.addRow("", self._transport_hint)

        # Connection status indicator
        self._conn_status_lbl = QLabel("● Disconnected")
        self._conn_status_lbl.setStyleSheet(
            f"color: {self.config.COLORS['text_muted']}; font-size: 10px; background: transparent;")
        conn_form.addRow("Status:", self._conn_status_lbl)

        # Buttons
        btn_row = QHBoxLayout()
        self._connect_btn     = self._make_btn("Connect to Server", accent=True, icon="fa5s.plug")
        self._disconnect_btn  = self._make_btn("Disconnect",         icon="fa5s.stop-circle")

        self._connect_btn.clicked.connect(self._on_connect)
        self._disconnect_btn.clicked.connect(self._on_disconnect)

        btn_row.addWidget(self._connect_btn)
        btn_row.addWidget(self._disconnect_btn)
        btn_row.addStretch()
        conn_form.addRow("", btn_row)
        layout.addWidget(conn_group)

        # ── Alert Thresholds ──────────────────────────────────────────────────
        layout.addWidget(SectionHeader("ALERT THRESHOLDS"))
        alert_group = self._make_group()
        alert_form = QFormLayout(alert_group)
        alert_form.setSpacing(10)
        alert_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.gyro_warn_spin  = self._make_spinbox(1000,  0,  5000, "units")
        self.gyro_crit_spin  = self._make_spinbox(2000,  0,  5000, "units")
        self.accel_warn_spin = self._make_spinbox(10000, 0, 32767, "units")
        self.accel_crit_spin = self._make_spinbox(15000, 0, 32767, "units")

        alert_form.addRow("Gyro Warning:",   self.gyro_warn_spin)
        alert_form.addRow("Gyro Critical:",  self.gyro_crit_spin)
        alert_form.addRow("Accel Warning:",  self.accel_warn_spin)
        alert_form.addRow("Accel Critical:", self.accel_crit_spin)
        layout.addWidget(alert_group)

        # ── Data Settings ──────────────────────────────────────────────────────
        layout.addWidget(SectionHeader("DATA SETTINGS"))
        data_group = self._make_group()
        data_form = QFormLayout(data_group)
        data_form.setSpacing(10)
        data_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.buffer_spin    = self._make_spinbox(500, 100,  5000, "readings")
        self.poll_rate_spin = self._make_spinbox(5,   1,   100,  "Hz")

        self.log_enabled     = self._make_checkbox("Enable system logging")
        self.log_enabled.setChecked(True)
        self.auto_reconnect  = self._make_checkbox("Auto-reconnect on disconnect")
        self.auto_reconnect.setChecked(True)

        data_form.addRow("Buffer Size:", self.buffer_spin)
        data_form.addRow("Poll Rate:",   self.poll_rate_spin)
        data_form.addRow("",             self.log_enabled)
        data_form.addRow("",             self.auto_reconnect)
        layout.addWidget(data_group)

        # ── AI & Data Processing ─────────────────────────────────────────────
        layout.addWidget(SectionHeader("AI & DATA PROCESSING"))
        ai_group = self._make_group()
        ai_form = QFormLayout(ai_group)
        ai_form.setSpacing(10)
        ai_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.ai_enabled = self._make_checkbox("Enable AI Anomaly Detection")
        self.ai_enabled.setChecked(True)
        
        from PyQt5.QtWidgets import QDoubleSpinBox
        self.ai_sensitivity_spin = QDoubleSpinBox()
        self.ai_sensitivity_spin.setRange(1.0, 10.0)
        self.ai_sensitivity_spin.setValue(3.0)
        self.ai_sensitivity_spin.setSingleStep(0.1)
        self.ai_sensitivity_spin.setSuffix("  Z")
        self.ai_sensitivity_spin.setFixedHeight(30)
        self.ai_sensitivity_spin.setFixedWidth(160)
        c = self.config.COLORS
        self.ai_sensitivity_spin.setStyleSheet(f"""
            QDoubleSpinBox {{
                background: {c['bg_secondary']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 4px; padding: 0 8px; font-size: 11px;
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background: {c['border']}; width: 16px;
            }}
        """)

        self.norm_range_spin = self._make_spinbox(0, 0, 32768, "Max")
        self.norm_range_spin.setToolTip("Normalize 16-bit sensor data (-32768 to 32767) to this range. 0 = Disabled.")

        ai_form.addRow("", self.ai_enabled)
        ai_form.addRow("AI Sensitivity:", self.ai_sensitivity_spin)
        ai_form.addRow("Norm Range (±):", self.norm_range_spin)
        layout.addWidget(ai_group)

        # ── Machine Management ────────────────────────────────────────────────
        layout.addWidget(SectionHeader("MACHINE MANAGEMENT"))
        machine_group = self._make_group()
        machine_layout = QVBoxLayout(machine_group)
        machine_layout.setSpacing(8)

        for machine in self.data_manager.get_all_machines():
            row = QHBoxLayout()
            lbl = QLabel(f"{machine.machine_id}  —  {machine.name}  ({machine.location})")
            lbl.setStyleSheet(f"color: {self.config.COLORS['text_primary']}; font-size: 11px; background: transparent;")
            status_dot = QLabel(f"● {machine.status}")
            status_dot.setStyleSheet(f"color: {machine.status_color}; font-size: 10px; background: transparent;")
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(status_dot)
            machine_layout.addLayout(row)
        layout.addWidget(machine_group)

        # ── Save / Reset row ─────────────────────────────────────────────────
        save_row = QHBoxLayout()
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {self.config.COLORS['accent_success']}; font-size: 10px;")
        reset_btn = self._make_btn("Reset to Defaults", icon="fa5s.undo")
        save_btn  = self._make_btn("Save Settings", accent=True, icon="fa5s.save")
        save_btn.setFixedWidth(160)
        reset_btn.setFixedWidth(160)
        reset_btn.clicked.connect(self._on_reset)
        save_btn.clicked.connect(self._on_save)

        save_row.addWidget(self._status_label)
        save_row.addStretch()
        save_row.addWidget(reset_btn)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)
        layout.addStretch()

        # Connect data_manager signals
        self.data_manager.connection_status_changed.connect(self._on_conn_status)

    # ─────────────────────────────────────────────────────────────────────────
    # Config load/save
    # ─────────────────────────────────────────────────────────────────────────

    def _load_saved_config(self):
        """Populate form fields from saved config."""
        cfg = connection_config.load()
        self.host_input.setText(str(cfg.get("host", "192.168.1.2")))
        self.port_input.setText(str(cfg.get("port", 5000)))
        tr = cfg.get("transport", "websocket")
        idx = self.transport_combo.findData(tr)
        self.transport_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.mqtt_host_input.setText(str(cfg.get("mqtt_host", "127.0.0.1")))
        self.mqtt_port_input.setText(str(cfg.get("mqtt_port", 1883)))
        self.mqtt_pattern_input.setText(str(cfg.get("mqtt_topic_pattern", "vimo/devices/+/data")))
        self._on_transport_changed()
        self.gyro_warn_spin.setValue(cfg.get("gyro_warn", 1000))
        self.gyro_crit_spin.setValue(cfg.get("gyro_crit", 2000))
        self.accel_warn_spin.setValue(cfg.get("accel_warn", 10000))
        self.accel_crit_spin.setValue(cfg.get("accel_crit", 15000))
        self.buffer_spin.setValue(cfg.get("buffer_size", 500))
        self.poll_rate_spin.setValue(cfg.get("poll_rate", 5))
        self.log_enabled.setChecked(cfg.get("log_enabled", True))
        self.auto_reconnect.setChecked(cfg.get("auto_reconnect", True))
        
        self.norm_range_spin.setValue(cfg.get("norm_range", 0))
        self.ai_enabled.setChecked(cfg.get("ai_enabled", True))
        self.ai_sensitivity_spin.setValue(cfg.get("ai_sensitivity", 3.0))

    def _collect_config(self) -> dict:
        """Read current form values into a config dict."""
        pat = self.mqtt_pattern_input.text().strip() or "vimo/devices/+/data"
        return {
            "host":               self.host_input.text().strip(),
            "port":               self._parse_port(),
            "transport":          self._current_transport(),
            "mqtt_host":          self.mqtt_host_input.text().strip() or "127.0.0.1",
            "mqtt_port":          self._parse_mqtt_port(),
            "mqtt_topic_pattern": pat,
            "gyro_warn":          self.gyro_warn_spin.value(),
            "gyro_crit":          self.gyro_crit_spin.value(),
            "accel_warn":         self.accel_warn_spin.value(),
            "accel_crit":         self.accel_crit_spin.value(),
            "buffer_size":        self.buffer_spin.value(),
            "poll_rate":          self.poll_rate_spin.value(),
            "log_enabled":        self.log_enabled.isChecked(),
            "auto_reconnect":     self.auto_reconnect.isChecked(),
            "norm_range":         self.norm_range_spin.value(),
            "ai_enabled":         self.ai_enabled.isChecked(),
            "ai_sensitivity":     self.ai_sensitivity_spin.value(),
        }

    def _parse_port(self) -> int:
        try:
            return int(self.port_input.text().strip())
        except ValueError:
            return 5000

    def _parse_mqtt_port(self) -> int:
        try:
            return int(self.mqtt_port_input.text().strip())
        except ValueError:
            return 1883

    def _current_transport(self) -> str:
        data = self.transport_combo.currentData()
        return str(data) if data else "websocket"

    @pyqtSlot()
    def _on_transport_changed(self):
        tr = self._current_transport()
        self._mqtt_container.setVisible(tr == "mqtt")
        if tr == "http":
            self._transport_hint.setText(
                "Mode HTTP hanya menyinkronkan daftar perangkat lewat REST; tidak ada aliran sensor real-time."
            )
        elif tr == "modbus":
            self._transport_hint.setText("Modbus TCP direncanakan pada rilis berikutnya.")
        else:
            self._transport_hint.setText("")

    # ─────────────────────────────────────────────────────────────────────────
    # Button handlers
    # ─────────────────────────────────────────────────────────────────────────

    @pyqtSlot()
    def _on_save(self):
        cfg = self._collect_config()
        ok = connection_config.save(cfg)
        if ok:
            self.data_manager.reload_runtime_config(cfg)
            self._flash_status("✔ Settings saved", success=True)
        else:
            self._flash_status("✘ Failed to save settings", success=False)

    @pyqtSlot()
    def _on_reset(self):
        from core.connection_config import _DEFAULTS
        cfg = dict(_DEFAULTS)
        connection_config.save(cfg)
        self.data_manager.reload_runtime_config(cfg)
        self._load_saved_config()
        self._flash_status("✔ Reset to defaults", success=True)

    @pyqtSlot()
    def _on_connect(self):
        if self._current_transport() == "modbus":
            QMessageBox.information(
                self,
                "Vimo",
                "Koneksi Modbus TCP belum tersedia. Pilih WebSocket, MQTT, atau HTTP.",
            )
            return
        cfg = self._collect_config()
        connection_config.save(cfg)  # auto-save before connecting
        self._flash_status(f"Connecting to {cfg['host']}:{cfg['port']} ...", success=True)
        self.data_manager.connect_server(cfg)

    @pyqtSlot()
    def _on_disconnect(self):
        self.data_manager.disconnect_server()

    @pyqtSlot(bool)
    def _on_conn_status(self, connected: bool):
        c = self.config.COLORS
        if connected:
            self._conn_status_lbl.setText("● Connected")
            self._conn_status_lbl.setStyleSheet(
                f"color: {c['accent_success']}; font-size: 10px; background: transparent;")
        else:
            self._conn_status_lbl.setText("● Disconnected")
            self._conn_status_lbl.setStyleSheet(
                f"color: {c['text_muted']}; font-size: 10px; background: transparent;")

    def _flash_status(self, msg: str, success: bool = True):
        c = self.config.COLORS
        color = c["accent_success"] if success else c["accent_danger"]
        self._status_label.setStyleSheet(f"color: {color}; font-size: 10px;")
        self._status_label.setText(msg)
        QTimer.singleShot(4000, lambda: self._status_label.setText(""))

    # ─────────────────────────────────────────────────────────────────────────
    # Widget factory helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _make_group(self) -> QGroupBox:
        group = QGroupBox()
        group.setStyleSheet(f"""
            QGroupBox {{
                background-color: {self.config.COLORS['bg_card']};
                border: 1px solid {self.config.COLORS['border']};
                border-radius: {self.config.LAYOUT['card_radius']}px;
                padding: 12px;
                margin: 0;
            }}
        """)
        return group

    def _make_input(self, placeholder: str = "", tooltip: str = "") -> QLineEdit:
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(30)
        if tooltip:
            inp.setToolTip(tooltip)
        c = self.config.COLORS
        inp.setStyleSheet(f"""
            QLineEdit {{
                background: {c['bg_secondary']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 4px;
                padding: 0 8px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border: 1px solid {c['accent']};
            }}
        """)
        return inp

    def _make_spinbox(self, default, min_val, max_val, suffix="") -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setSuffix(f"  {suffix}")
        spin.setFixedHeight(30)
        spin.setFixedWidth(160)
        c = self.config.COLORS
        spin.setStyleSheet(f"""
            QSpinBox {{
                background: {c['bg_secondary']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 4px;
                padding: 0 8px;
                font-size: 11px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: {c['border']};
                width: 16px;
            }}
        """)
        return spin

    def _make_checkbox(self, label: str) -> QCheckBox:
        cb = QCheckBox(label)
        cb.setStyleSheet(f"color: {self.config.COLORS['text_primary']}; font-size: 11px;")
        return cb

    def _make_btn(self, label: str, accent: bool = False, icon: str = None) -> QPushButton:
        btn = QPushButton()
        if label:
            btn.setText(f"  {label}")
        btn.setFixedHeight(32)
        btn.setCursor(Qt.PointingHandCursor)
        if icon:
            c = self.config.COLORS
            color = "white" if accent else c["text_muted"]
            ic = _icon(icon, color=color)
            if ic:
                btn.setIcon(ic)
        c = self.config.COLORS
        if accent:
            style = f"""
                QPushButton {{
                    background: {c['accent']};
                    color: #ffffff;
                    border: none;
                    border-radius: 4px;
                    font-size: 11px;
                    padding: 0 16px;
                    font-weight: bold;
                    text-align: left;
                }}
                QPushButton:hover {{ background: {c['accent_hover']}; }}
            """
        else:
            style = f"""
                QPushButton {{
                    background: {c['bg_secondary']};
                    color: {c['text_secondary']};
                    border: 1px solid {c['border']};
                    border-radius: 4px;
                    font-size: 11px;
                    padding: 0 16px;
                    text-align: left;
                }}
                QPushButton:hover {{ background: {c['bg_card']}; color: {c['text_primary']}; }}
            """
        btn.setStyleSheet(style)
        return btn
