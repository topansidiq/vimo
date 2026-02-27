"""
Real-time chart widget menggunakan Matplotlib embedded di PyQt5.

Optimasi performa:
- _dirty flag: canvas hanya di-redraw jika ada data baru
- draw_idle() dipakai (bukan draw()) — non-blocking
- autoscale hanya di-update per N refresh (bukan setiap frame)
- Jumlah titik dibatasi (max_points) agar line rendering cepat
- Blit (background caching) untuk render diferensial yang jauh lebih cepat

Interaktivitas:
- Mouse wheel zoom (Y-axis) untuk semua 2D chart
- Mouse wheel zoom (XYZ) untuk semua 3D chart
- Detail Mode: tombol untuk lock/unlock autoscale sehingga threshold tetap terlihat
- Font Awesome icons via qtawesome
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog
from PyQt5.QtCore import Qt, pyqtSlot, QTimer
import qtawesome as qta
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import matplotlib.ticker as ticker
from collections import deque
from datetime import datetime
from typing import Dict, Optional, List
import numpy as np
from mpl_toolkits.mplot3d import Axes3D

from core.app_config import AppConfig


# ─── Shared icon helper ───────────────────────────────────────────────────────
def _icon(name: str, color: str = "#9e9e9e", size: int = 12):
    """Return a QIcon from Font Awesome via qtawesome."""
    try:
        return qta.icon(name, color=color, scale_factor=1.0)
    except Exception:
        return None

class _ChartCanvas(FigureCanvas):
    """
    Custom canvas that consumes wheel events so they don't bubble up
    to a parent QScrollArea and cause the page to scroll instead of
    zooming the chart.
    """
    def __init__(self, figure):
        super().__init__(figure)
        self._is_panning = False
        self._pan_start_y = 0
        self._pan_start_ylim = None

    def wheelEvent(self, event):
        # Accept the Qt event first (stops propagation to scroll area)
        event.accept()
        # Still forward to matplotlib so _on_scroll fires
        super().wheelEvent(event)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self._is_panning = True
            self._pan_start_y = event.y()
            # Find the axes associated with this canvas to get current Y limits
            if self.figure.axes:
                self._pan_start_ylim = self.figure.axes[0].get_ylim()
            # Also notify parents we are detailing so autoscale stops acting up
            if hasattr(self.parent(), '_detail_mode') and not self.parent()._detail_mode:
                self.parent()._toggle_detail(True)
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        if self._is_panning and self._pan_start_ylim and self.figure.axes:
            ax = self.figure.axes[0]
            # Calculate pixel difference
            dy_pixels = event.y() - self._pan_start_y
            
            # Convert pixel difference to data coordinates
            # A rough estimation based on the bounding box height
            bbox = ax.get_window_extent()
            data_range = self._pan_start_ylim[1] - self._pan_start_ylim[0]
            pixel_height = bbox.height
            
            if pixel_height > 0:
                dy_data = (dy_pixels / pixel_height) * data_range
                # When dragging mouse down (dy > 0), the view shifts up, so we add dy_data
                ax.set_ylim(self._pan_start_ylim[0] + dy_data, self._pan_start_ylim[1] + dy_data)
                self.draw_idle()
        super().mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self._is_panning = False
            self._pan_start_ylim = None
        super().mouseReleaseEvent(event)


class RealtimeChart(QWidget):
    """
    High-performance real-time line chart.
    - Gunakan push() untuk tambah data
    - Gunakan refresh() dari timer — chart HANYA dirender ulang jika dirty
    - Scroll wheel: zoom Y axis
    - Detail button: lock autoscale (threshold lines stay visible)
    """

    def __init__(self, title: str = "", y_label: str = "",
                 max_points: int = 120, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self._max_points = max_points
        self._series: Dict[str, deque] = {}
        self._lines:  Dict[str, Line2D] = {}
        self._threshold_lines: List = []
        self._dirty   = False
        self._autoscale_counter = 0
        self._AUTOSCALE_EVERY   = 5
        self._detail_mode = False   # When True, autoscale is locked

        self._build_chart(title, y_label)

    def _build_chart(self, title: str, y_label: str):
        c   = self.config.COLORS
        bg  = c["chart_bg"]
        fg  = c["text_secondary"]
        grid = c["border"]

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Toolbar row ──────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 0)
        toolbar.setSpacing(4)

        toolbar.addStretch()

        # Detail zoom button (lock autoscale)
        self._detail_btn = QPushButton()
        self._detail_btn.setFixedSize(22, 18)
        self._detail_btn.setCursor(Qt.PointingHandCursor)
        self._detail_btn.setToolTip("Detail Mode: lock zoom so threshold stays visible")
        ic = _icon("fa5s.search-plus", color=c["text_muted"])
        if ic:
            self._detail_btn.setIcon(ic)
        else:
            self._detail_btn.setText("+")
        self._detail_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['bg_secondary']};
                border: 1px solid {c['border']};
                border-radius: 3px;
            }}
            QPushButton:hover {{ border-color: {c['accent']}; }}
            QPushButton:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}
        """)
        self._detail_btn.setCheckable(True)
        self._detail_btn.clicked.connect(self._toggle_detail)
        toolbar.addWidget(self._detail_btn)

        # Reset / Home button — exits detail mode, restores full autoscale immediately
        self._reset_btn = QPushButton()
        self._reset_btn.setFixedSize(22, 18)
        self._reset_btn.setCursor(Qt.PointingHandCursor)
        self._reset_btn.setToolTip("Reset View — return to auto-tracking / full data view")
        ic_r = _icon("fa5s.home", color=c["text_muted"])
        if ic_r:
            self._reset_btn.setIcon(ic_r)
        else:
            self._reset_btn.setText("⌂")
        self._reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['bg_secondary']};
                border: 1px solid {c['border']};
                border-radius: 3px;
            }}
            QPushButton:hover {{ border-color: {c['accent_success']}; }}
        """)
        self._reset_btn.clicked.connect(self._reset_view)
        toolbar.addWidget(self._reset_btn)

        outer.addLayout(toolbar)

        # ── Matplotlib figure ─────────────────────────────────────────────────
        self.figure = Figure(figsize=(5, 2.5), dpi=80, facecolor=bg)
        self.figure.subplots_adjust(left=0.1, right=0.98, top=0.88, bottom=0.08)

        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor(bg)
        self.ax.tick_params(colors=fg, labelsize=7)
        self.ax.yaxis.label.set_color(fg)

        for spine in self.ax.spines.values():
            spine.set_edgecolor(grid)

        self.ax.grid(True, color=grid, linewidth=0.4, alpha=0.5)
        self.ax.set_ylabel(y_label, color=fg, fontsize=8)
        self.ax.xaxis.set_major_formatter(ticker.NullFormatter())
        self.ax.xaxis.set_ticks([])

        if title:
            self.ax.set_title(title, color=fg, fontsize=9, pad=4)

        self.canvas = _ChartCanvas(self.figure)
        self.canvas.setStyleSheet(f"background-color: {bg};")
        outer.addWidget(self.canvas)

        # Connect zoom events
        self.canvas.mpl_connect('scroll_event', self._on_scroll)

    def _toggle_detail(self, checked: bool):
        """Lock autoscale for detail inspection."""
        self._detail_mode = checked
        c = self.config.COLORS
        if checked:
            ic = _icon("fa5s.search-minus", color="white")
            self._detail_btn.setToolTip("Detail Mode ON — click to exit")
        else:
            self._reset_view()
            return
        if ic:
            self._detail_btn.setIcon(ic)

    def _reset_view(self):
        """Exit detail mode and immediately restore full autoscale."""
        self._detail_mode = False
        self._detail_btn.setChecked(False)
        c = self.config.COLORS
        ic = _icon("fa5s.search-plus", color=c["text_muted"])
        if ic:
            self._detail_btn.setIcon(ic)
        self._detail_btn.setToolTip("Detail Mode: lock zoom so threshold stays visible")
        # Immediately restore to full data view
        self.ax.relim()
        self.ax.autoscale_view(scalex=True, scaley=True)
        self._autoscale_counter = 0
        self._dirty = True
        self.canvas.draw_idle()

    def add_series(self, name: str, color: str, label: Optional[str] = None):
        """Daftarkan series baru. Panggil sebelum push()."""
        self._series[name] = deque(maxlen=self._max_points)
        lbl = label or name
        line, = self.ax.plot([], [], color=color, linewidth=1.0,
                             label=lbl, antialiased=True)
        self._lines[name] = line

        if len(self._series) > 1:
            self.ax.legend(
                facecolor=self.config.COLORS["bg_card"],
                edgecolor=self.config.COLORS["border"],
                labelcolor=self.config.COLORS["text_secondary"],
                fontsize=7, loc="upper left",
            )

    def add_threshold(self, value: float, color: str = "#ff9800", label: str = "Threshold"):
        """Add a horizontal threshold line that always stays visible."""
        line = self.ax.axhline(y=value, color=color, linewidth=1.0,
                                linestyle="--", alpha=0.8, label=label, zorder=5)
        self._threshold_lines.append(line)
        return line

    def push(self, series_name: str, value: float, _timestamp=None):
        if series_name in self._series:
            self._series[series_name].append(value)
            self._dirty = True

    def refresh(self):
        if not self._dirty or not self._series or not self.isVisible():
            return
        self._dirty = False

        n = max(len(v) for v in self._series.values())
        if n == 0:
            return

        x = list(range(n))
        for name, line in self._lines.items():
            y = list(self._series[name])
            xn = x[-len(y):] if len(x) > len(y) else x
            line.set_xdata(xn)
            line.set_ydata(y)

        # Only autoscale if NOT in detail mode
        if not self._detail_mode:
            self._autoscale_counter += 1
            if self._autoscale_counter >= self._AUTOSCALE_EVERY:
                self._autoscale_counter = 0
                self.ax.relim()
                self.ax.autoscale_view(scalex=True, scaley=True)
                # Also update x-axis to show latest window
                self.ax.set_xlim(left=max(0, n - self._max_points), right=n - 1)

        self.canvas.draw_idle()

    def _on_scroll(self, event):
        """Dynamic zoom in/out with mouse wheel (both axes)."""
        if event.inaxes != self.ax:
            return

        # Activate detail mode and update icon if not already active
        if not self._detail_mode:
            self._detail_mode = True
            self._detail_btn.setChecked(True)
            ic = _icon("fa5s.search-minus", color="white")
            if ic:
                self._detail_btn.setIcon(ic)
            self._detail_btn.setToolTip("Detail Mode ON — click 🏠 to reset view")

        base_scale = 1.15
        scale_factor = 1 / base_scale if event.button == 'up' else base_scale

        # Zoom Y axis
        cur_ylim = self.ax.get_ylim()
        mid_y = (cur_ylim[1] + cur_ylim[0]) / 2
        half_y = (cur_ylim[1] - cur_ylim[0]) * scale_factor / 2
        self.ax.set_ylim([mid_y - half_y, mid_y + half_y])

        # Zoom X axis
        cur_xlim = self.ax.get_xlim()
        mid_x = (cur_xlim[1] + cur_xlim[0]) / 2
        half_x = (cur_xlim[1] - cur_xlim[0]) * scale_factor / 2
        self.ax.set_xlim([mid_x - half_x, mid_x + half_x])

        self.canvas.draw_idle()


class DualModeChart(QWidget):
    """
    Chart dengan toggle antara RAW dan FILTERED (Kalman) data.
    Menampilkan dua set series sekaligus — raw (tipis) dan filtered (tebal).
    """

    SERIES_DEFS = {
        "accel": [
            ("ax_r", "ax_f", "Accel X", "#4a9eff66", "#4a9eff"),
            ("ay_r", "ay_f", "Accel Y", "#4caf5066", "#4caf50"),
            ("az_r", "az_f", "Accel Z", "#ff980066", "#ff9800"),
        ],
        "gyro": [
            ("gx_r", "gx_f", "Gyro X", "#e91e6366", "#e91e63"),
            ("gy_r", "gy_f", "Gyro Y", "#9c27b066", "#9c27b0"),
            ("gz_r", "gz_f", "Gyro Z", "#00bcd466", "#00bcd4"),
        ],
    }

    def __init__(self, mode: str = "accel", machine_name: str = "", parent=None):
        """mode: 'accel' atau 'gyro'"""
        super().__init__(parent)
        self.config   = AppConfig()
        self._mode    = mode
        self._show_raw = True

        title_map = {"accel": f"Accelerometer — {machine_name}",
                     "gyro":  f"Gyroscope — {machine_name}"}
        self._chart = RealtimeChart(
            title=title_map.get(mode, mode),
            y_label="Value (LSB)",
            max_points=120,
        )

        for raw_k, flt_k, label, raw_c, flt_c in self.SERIES_DEFS[mode]:
            self._chart.add_series(raw_k, raw_c, f"{label} raw")
            self._chart.add_series(flt_k, flt_c, f"{label} filtered")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Toggle raw button
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(4, 0, 4, 0)
        self._toggle_btn = QPushButton()
        self._toggle_btn.setFixedHeight(20)
        self._toggle_btn.setFixedWidth(90)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        c = self.config.COLORS
        ic = _icon("fa5s.eye-slash", color=c["text_muted"])
        if ic:
            self._toggle_btn.setIcon(ic)
            self._toggle_btn.setText("  Hide Raw")
        else:
            self._toggle_btn.setText("Hide Raw")
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['bg_secondary']};
                color: {c['text_muted']};
                border: 1px solid {c['border']};
                border-radius: 3px; font-size: 9px;
                text-align: left; padding-left: 4px;
            }}
            QPushButton:hover {{ color: {c['text_primary']}; }}
        """)
        self._toggle_btn.clicked.connect(self._toggle_raw)
        btn_row.addStretch()
        btn_row.addWidget(self._toggle_btn)
        layout.addLayout(btn_row)
        layout.addWidget(self._chart)

    def _toggle_raw(self):
        self._show_raw = not self._show_raw
        c = self.config.COLORS
        if self._show_raw:
            ic = _icon("fa5s.eye-slash", color=c["text_muted"])
            self._toggle_btn.setText("  Hide Raw")
        else:
            ic = _icon("fa5s.eye", color=c["text_muted"])
            self._toggle_btn.setText("  Show Raw")
        if ic:
            self._toggle_btn.setIcon(ic)
        for raw_k, flt_k, label, _, _ in self.SERIES_DEFS[self._mode]:
            line = self._chart._lines.get(raw_k)
            if line:
                line.set_visible(self._show_raw)
        self._chart._dirty = True

    def update_reading(self, reading):
        if self._mode == "accel":
            pairs = [
                ("ax_r", reading.accel_x),    ("ax_f", reading.accel_x_f or reading.accel_x),
                ("ay_r", reading.accel_y),    ("ay_f", reading.accel_y_f or reading.accel_y),
                ("az_r", reading.accel_z),    ("az_f", reading.accel_z_f or reading.accel_z),
            ]
        else:
            pairs = [
                ("gx_r", reading.gyro_x),    ("gx_f", reading.gyro_x_f or reading.gyro_x),
                ("gy_r", reading.gyro_y),    ("gy_f", reading.gyro_y_f or reading.gyro_y),
                ("gz_r", reading.gyro_z),    ("gz_f", reading.gyro_z_f or reading.gyro_z),
            ]
        for key, val in pairs:
            self._chart.push(key, val)

    def refresh(self):
        self._chart.refresh()


# ─── 3D Base Mixin ────────────────────────────────────────────────────────────
class _3DChartMixin:
    """Shared helpers for 3D charts."""

    def _make_expand_btn(self, c):
        btn = QPushButton()
        btn.setFixedSize(72, 18)
        btn.setCursor(Qt.PointingHandCursor)
        ic = _icon("fa5s.expand-arrows-alt", color=c["text_muted"])
        if ic:
            btn.setIcon(ic)
            btn.setText("  FULLSCR")
        else:
            btn.setText("⊡ FULLSCR")
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['bg_secondary']};
                color: {c['text_muted']};
                border: 1px solid {c['border']};
                border-radius: 2px; font-size: 8px;
                text-align: left; padding-left: 4px;
            }}
            QPushButton:hover {{ color: white; background: {c['accent']}; }}
        """)
        return btn

    def _3d_scroll_zoom(self, event):
        if event.inaxes != self.ax: return
        base_scale = 1.15
        sf = 1/base_scale if event.button == 'up' else base_scale
        for set_l, get_l in [(self.ax.set_xlim3d, self.ax.get_xlim3d),
                              (self.ax.set_ylim3d, self.ax.get_ylim3d),
                              (self.ax.set_zlim3d, self.ax.get_zlim3d)]:
            l, h = get_l()
            m = (l + h) / 2
            s = (h - l) * sf
            set_l(m - s/2, m + s/2)
        self.canvas.draw_idle()


class TrajectoryChart(_3DChartMixin, QWidget):
    """
    Trajectory Chart - Visualisasi pergerakan 3D (Accel X, Y, Z).
    """

    def __init__(self, machine_name: str = "", max_points: int = 50, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self._machine_name = machine_name
        self._max_points = max_points
        self._x_data = deque(maxlen=max_points)
        self._y_data = deque(maxlen=max_points)
        self._z_data = deque(maxlen=max_points)
        self._dirty = False
        self._lock_limits = False  # When True, skip recalculating axis limits (fullscreen mode)

        self._build_chart(machine_name)

    def _build_chart(self, machine_name: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        c = self.config.COLORS

        # Header with expand button
        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 4, 0)

        self._expand_btn = self._make_expand_btn(c)
        self._expand_btn.clicked.connect(self._on_expand)
        header.addStretch()
        header.addWidget(self._expand_btn)
        layout.addLayout(header)

        bg = c["chart_bg"]
        fg = c["text_secondary"]
        grid = c["border"]

        self.figure = Figure(figsize=(4, 4), dpi=80, facecolor=bg)
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.ax.set_facecolor(bg)
        self.ax.tick_params(colors=fg, labelsize=7)
        self.ax.xaxis.pane.fill = False
        self.ax.yaxis.pane.fill = False
        self.ax.zaxis.pane.fill = False
        self.ax.xaxis.pane.set_edgecolor(grid)
        self.ax.yaxis.pane.set_edgecolor(grid)
        self.ax.zaxis.pane.set_edgecolor(grid)

        self.ax.set_title(f"3D Trajectory (Accel) - {machine_name}", color=fg, fontsize=9, pad=4)
        self.ax.set_xlabel("Accel X (F)", color=fg, fontsize=8)
        self.ax.set_ylabel("Accel Y (F)", color=fg, fontsize=8)
        self.ax.set_zlabel("Accel Z (F)", color=fg, fontsize=8)

        # Plot 3D line
        self._line, = self.ax.plot([], [], [], color=c["accent"], linewidth=1.5, alpha=0.8)
        self._head, = self.ax.plot([], [], [], 'o', color=c["accent"], markersize=4)

        # Coordinate axes (XYZ guide lines) - RGB — thicker
        self._axis_x, = self.ax.plot([], [], [], color='#FF5B5B', linewidth=2.5, linestyle="-", alpha=0.85)  # Red
        self._axis_y, = self.ax.plot([], [], [], color='#5BFF5B', linewidth=2.5, linestyle="-", alpha=0.85)  # Green
        self._axis_z, = self.ax.plot([], [], [], color='#5B8BFF', linewidth=2.5, linestyle="-", alpha=0.85)  # Blue

        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        self.canvas.mpl_connect('scroll_event', self._on_scroll)

    def _on_expand(self):
        dialog = ChartDialog("trajectory", self._machine_name, self)
        dialog.exec_()

    def update_reading(self, reading):
        x = reading.accel_x_f if reading.accel_x_f is not None else reading.accel_x
        y = reading.accel_y_f if reading.accel_y_f is not None else reading.accel_y
        z = reading.accel_z_f if reading.accel_z_f is not None else reading.accel_z
        self._x_data.append(x)
        self._y_data.append(y)
        self._z_data.append(z)
        self._dirty = True

    def refresh(self):
        if not self._dirty or not self._x_data or not self.isVisible():
            return
        self._dirty = False

        x = list(self._x_data)
        y = list(self._y_data)
        z = list(self._z_data)

        self._line.set_data(x, y)
        self._line.set_3d_properties(z)
        if x:
            self._head.set_data([x[-1]], [y[-1]])
            self._head.set_3d_properties([z[-1]])

        # Only update axis limits if not locked (locked = user is rotating in fullscreen)
        if not self._lock_limits and len(x) > 0:
            limit_x = max(abs(min(x)), abs(max(x))) + 10
            limit_y = max(abs(min(y)), abs(max(y))) + 10
            limit_z = max(abs(min(z)), abs(max(z))) + 10

            self.ax.set_xlim3d(-limit_x, limit_x)
            self.ax.set_ylim3d(-limit_y, limit_y)
            self.ax.set_zlim3d(-limit_z, limit_z)

            self._axis_x.set_data([-limit_x, limit_x], [0, 0])
            self._axis_x.set_3d_properties([0, 0])
            self._axis_y.set_data([0, 0], [-limit_y, limit_y])
            self._axis_y.set_3d_properties([0, 0])
            self._axis_z.set_data([0, 0], [0, 0])
            self._axis_z.set_3d_properties([-limit_z, limit_z])

        self.canvas.draw_idle()

    def _on_scroll(self, event):
        self._3d_scroll_zoom(event)


class ScatterPlotChart(_3DChartMixin, QWidget):
    """
    Scatter Plot - Visualisasi korelasi Gyro X, Y, Z dalam 3D.
    """

    def __init__(self, machine_name: str = "", max_points: int = 100, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self._machine_name = machine_name
        self._max_points = max_points
        self._x_data = deque(maxlen=max_points)
        self._y_data = deque(maxlen=max_points)
        self._z_data = deque(maxlen=max_points)
        self._dirty = False
        self._lock_limits = False

        self._build_chart(machine_name)

    def _build_chart(self, machine_name: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        c = self.config.COLORS

        # Header with expand button
        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 4, 0)

        self._expand_btn = self._make_expand_btn(c)
        self._expand_btn.clicked.connect(self._on_expand)
        header.addStretch()
        header.addWidget(self._expand_btn)
        layout.addLayout(header)

        bg = c["chart_bg"]
        fg = c["text_secondary"]
        grid = c["border"]

        self.figure = Figure(figsize=(4, 4), dpi=80, facecolor=bg)
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.ax.set_facecolor(bg)
        self.ax.tick_params(colors=fg, labelsize=7)
        self.ax.xaxis.pane.fill = False
        self.ax.yaxis.pane.fill = False
        self.ax.zaxis.pane.fill = False
        self.ax.xaxis.pane.set_edgecolor(grid)
        self.ax.yaxis.pane.set_edgecolor(grid)
        self.ax.zaxis.pane.set_edgecolor(grid)

        self.ax.set_title(f"3D Gyro Scatter - {machine_name}", color=fg, fontsize=9, pad=4)
        self.ax.set_xlabel("Gyro X (F)", color=fg, fontsize=8)
        self.ax.set_ylabel("Gyro Y (F)", color=fg, fontsize=8)
        self.ax.set_zlabel("Gyro Z (F)", color=fg, fontsize=8)

        self._scatter = self.ax.scatter([], [], [], s=10, color=c["accent_info"], alpha=0.6)
        self._line, = self.ax.plot([], [], [], color=c["accent_info"], linewidth=0.8, alpha=0.4)

        # Coordinate axes — thicker
        self._axis_x, = self.ax.plot([], [], [], color='#FF5B5B', linewidth=2.5, linestyle="-", alpha=0.85)
        self._axis_y, = self.ax.plot([], [], [], color='#5BFF5B', linewidth=2.5, linestyle="-", alpha=0.85)
        self._axis_z, = self.ax.plot([], [], [], color='#5B8BFF', linewidth=2.5, linestyle="-", alpha=0.85)

        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        self.canvas.mpl_connect('scroll_event', self._on_scroll)

    def _on_expand(self):
        dialog = ChartDialog("scatter", self._machine_name, self)
        dialog.exec_()

    def update_reading(self, reading):
        x = reading.gyro_x_f if reading.gyro_x_f is not None else reading.gyro_x
        y = reading.gyro_y_f if reading.gyro_y_f is not None else reading.gyro_y
        z = reading.gyro_z_f if reading.gyro_z_f is not None else reading.gyro_z
        self._x_data.append(x)
        self._y_data.append(y)
        self._z_data.append(z)
        self._dirty = True

    def refresh(self):
        if not self._dirty or not self._x_data or not self.isVisible():
            return
        self._dirty = False

        x = list(self._x_data)
        y = list(self._y_data)
        z = list(self._z_data)

        self._scatter._offsets3d = (x, y, z)
        self._line.set_data(x, y)
        self._line.set_3d_properties(z)

        if not self._lock_limits and len(x) > 0:
            limit_x = max(abs(min(x)), abs(max(x))) + 50
            limit_y = max(abs(min(y)), abs(max(y))) + 50
            limit_z = max(abs(min(z)), abs(max(z))) + 50

            self.ax.set_xlim3d(-limit_x, limit_x)
            self.ax.set_ylim3d(-limit_y, limit_y)
            self.ax.set_zlim3d(-limit_z, limit_z)

            self._axis_x.set_data([-limit_x, limit_x], [0, 0])
            self._axis_x.set_3d_properties([0, 0])
            self._axis_y.set_data([0, 0], [-limit_y, limit_y])
            self._axis_y.set_3d_properties([0, 0])
            self._axis_z.set_data([0, 0], [0, 0])
            self._axis_z.set_3d_properties([-limit_z, limit_z])

        self.canvas.draw_idle()

    def _on_scroll(self, event):
        self._3d_scroll_zoom(event)


class ChartDialog(QDialog):
    """
    Dialog fullscreen untuk chart 3D.
    - Menyinkronisasi data dari parent widget
    - Menjaga posisi rotasi pengguna (tidak reset saat data diperbarui)
    - Memiliki button Lock/Unlock untuk menghentikan auto-pivot
    """

    def __init__(self, chart_type: str, machine_name: str, parent_widget: QWidget):
        super().__init__(parent_widget)
        self.config = AppConfig()
        self.chart_type = chart_type
        self.machine_name = machine_name
        self.parent_widget = parent_widget

        self.setWindowTitle(f"Expanded View — {machine_name}")
        self.resize(900, 700)
        self.setStyleSheet(f"background-color: {self.config.COLORS['bg_primary']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Toolbar ──────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        c = self.config.COLORS

        # Title
        title_lbl = QLabel(f"{'3D Trajectory' if chart_type == 'trajectory' else '3D Scatter'} — {machine_name}")
        title_lbl.setStyleSheet(f"color: {c['text_primary']}; font-size: 13px; font-weight: bold;")
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()

        # Lock rotation button
        self._lock_btn = QPushButton()
        self._lock_btn.setFixedHeight(24)
        self._lock_btn.setCheckable(True)
        self._lock_btn.setCursor(Qt.PointingHandCursor)
        ic_lock = _icon("fa5s.lock-open", color=c["text_muted"])
        if ic_lock:
            self._lock_btn.setIcon(ic_lock)
            self._lock_btn.setText("  Live Update")
        else:
            self._lock_btn.setText("Live Update")
        self._lock_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['bg_secondary']};
                color: {c['text_muted']};
                border: 1px solid {c['border']};
                border-radius: 3px; font-size: 9px;
                padding: 0 8px;
            }}
            QPushButton:checked {{
                background: {c['accent']};
                color: white;
                border-color: {c['accent']};
            }}
            QPushButton:hover {{ color: {c['text_primary']}; }}
        """)
        self._lock_btn.clicked.connect(self._on_lock_toggle)
        toolbar.addWidget(self._lock_btn)

        layout.addLayout(toolbar)

        # ── Chart ─────────────────────────────────────────────────────────────
        if chart_type == "trajectory":
            self.chart = TrajectoryChart(machine_name, max_points=300)
            self.chart._expand_btn.hide()
        else:
            self.chart = ScatterPlotChart(machine_name, max_points=600)
            self.chart._expand_btn.hide()

        # Lock axis updates so user rotation is preserved
        self.chart._lock_limits = True

        layout.addWidget(self.chart)

        # ── Sync timer ────────────────────────────────────────────────────────
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self._sync_data)
        self.sync_timer.start(100)

    def _on_lock_toggle(self, checked: bool):
        """Toggle whether axis limits update (which resets rotation) or not."""
        c = self.config.COLORS
        # When checked = "lock axis" = keep user rotation = lock_limits True
        # When unchecked = "live update" = allow axis to track data = lock_limits False
        self.chart._lock_limits = not checked  # Inverted: checked means "lock"
        if checked:
            ic = _icon("fa5s.lock", color="white")
            self._lock_btn.setText("  Rotation Locked")
        else:
            ic = _icon("fa5s.lock-open", color=c["text_muted"])
            self._lock_btn.setText("  Live Update")
        if ic:
            self._lock_btn.setIcon(ic)

    def _sync_data(self):
        """Mirror data from parent widget into dialog chart."""
        self.chart._x_data = self.parent_widget._x_data
        self.chart._y_data = self.parent_widget._y_data
        self.chart._z_data = self.parent_widget._z_data
        self.chart._dirty = True
        self.chart.refresh()
