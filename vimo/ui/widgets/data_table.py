"""
Live data table dengan buffered batch update.

Optimasi performa:
- Tidak insert/remove row setiap data masuk
- Data dikumpulkan di buffer internal
- Tabel di-refresh sekaligus dari timer (bukan per event)
- Gunakan setItem() bukan insertRow() untuk update in-place
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush

from collections import deque
from core.app_config import AppConfig


class LiveDataTable(QWidget):
    """
    Tabel real-time yang menampilkan N baris terakhir sensor readings.
    Update dilakukan secara batch — bukan per-reading — untuk performa optimal.
    """

    COLUMNS = ["Timestamp", "Machine", "AccX (raw)", "AccX (flt)",
               "GyroX (raw)", "GyroX (flt)", "Acc Mag", "Gyro Mag",
               "Vibration", "Status"]

    MAX_ROWS    = 30    # Tampilkan 30 baris terakhir
    BUFFER_SIZE = 200   # Simpan 200 reading di memori

    STATUS_COLORS = {
        "Normal":   "#4caf50",
        "Warning":  "#ff9800",
        "Critical": "#f44336",
    }
    VIBRATION_COLORS = {
        "Normal":   "#4caf50",
        "Elevated": "#ff9800",
        "High":     "#ff5722",
        "Critical": "#f44336",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config   = AppConfig()
        self._buffer: deque = deque(maxlen=self.BUFFER_SIZE)  # (machine_id, reading)
        self._need_refresh = False
        self._build_ui()

        # Refresh tabel setiap 400ms (tidak perlu lebih cepat dari ini)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._flush_to_table)
        self._refresh_timer.start(400)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setRowCount(self.MAX_ROWS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setSortingEnabled(False)

        # Row height lebih kecil → lebih banyak data terlihat
        self.table.verticalHeader().setDefaultSectionSize(20)

        header = self.table.horizontalHeader()
        for i in range(len(self.COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)

        c = self.config.COLORS
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: {self.config.LAYOUT['card_radius']}px;
                gridline-color: {c['border']};
                font-size: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
            }}
            QTableWidget::item {{ padding: 1px 4px; }}
            QTableWidget::item:selected {{
                background-color: {c['sidebar_item_active']};
            }}
            QHeaderView::section {{
                background-color: {c['bg_secondary']};
                color: {c['text_secondary']};
                border: none;
                border-bottom: 1px solid {c['border']};
                padding: 3px 4px;
                font-size: 9px;
                font-weight: bold;
            }}
        """)
        layout.addWidget(self.table)

    def add_row(self, machine_id: str, reading):
        """Tambahkan reading ke buffer. TIDAK langsung update tabel."""
        self._buffer.appendleft((machine_id, reading))
        self._need_refresh = True

    def _flush_to_table(self):
        """
        Update tabel secara batch dari buffer.
        Dipanggil oleh timer, bukan oleh setiap data masuk.
        """
        if not self._need_refresh:
            return
        self._need_refresh = False

        rows = list(self._buffer)[:self.MAX_ROWS]

        self.table.setUpdatesEnabled(False)
        for row_idx, (machine_id, reading) in enumerate(rows):
            if row_idx >= self.MAX_ROWS:
                break

            ax_r = f"{reading.accel_x:.0f}"
            ax_f = f"{reading.accel_x_f:.1f}" if reading.accel_x_f is not None else "—"
            gx_r = f"{reading.gyro_x:.0f}"
            gx_f = f"{reading.gyro_x_f:.1f}" if reading.gyro_x_f is not None else "—"

            status = reading.status
            vibration = reading.vibration_level
            s_color = self.STATUS_COLORS.get(status, "#9e9e9e")
            v_color = self.VIBRATION_COLORS.get(vibration, "#9e9e9e")

            values = [
                reading.timestamp.strftime("%H:%M:%S.%f")[:-4],
                machine_id,
                ax_r, ax_f,
                gx_r, gx_f,
                f"{reading.accel_magnitude_f:.0f}",
                f"{reading.gyro_magnitude_f:.0f}",
                vibration,
                status,
            ]

            for col, val in enumerate(values):
                item = self.table.item(row_idx, col)
                if item is None:
                    item = QTableWidgetItem()
                    item.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row_idx, col, item)
                item.setText(val)

                # Warna khusus kolom tertentu
                if col == 8:   # vibration
                    item.setForeground(QBrush(QColor(v_color)))
                elif col == 9: # status
                    item.setForeground(QBrush(QColor(s_color)))
                else:
                    item.setForeground(QBrush(QColor(self.config.COLORS["text_primary"])))

        self.table.setUpdatesEnabled(True)
