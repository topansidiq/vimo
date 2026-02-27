"""
Sidebar navigation widget — with Font Awesome icons via qtawesome.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSizePolicy, QSpacerItem, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QIcon, QCursor
import qtawesome as qta

from core.app_config import AppConfig


def _icon(name, color="#9e9e9e", size=14):
    try:
        return qta.icon(name, color=color, scale_factor=1.0)
    except Exception:
        return None


# Nav definitions: (fa_icon_name, label, page_id, fallback_char)
_NAV_DEFS = [
    ("fa5s.tachometer-alt", "Dashboard", "dashboard", "D"),
    ("fa5s.bolt", "Activity", "activity", "A"),
    ("fa5s.chart-bar", "Log & Statistics", "log_statistic", "L"),
    ("fa5s.microchip", "Devices", "devices", "V"),
    ("fa5s.boxes", "Assets", "assets", "S"),
    ("fa5s.cog", "Settings", "settings", "C"),
]


class SidebarItem(QPushButton):
    """A single navigation item in the sidebar — uses qtawesome icon."""

    def __init__(self, fa_name: str, fallback: str, label: str, page_id: str, parent=None):
        super().__init__(parent)
        self.page_id = page_id
        self._fa_name = fa_name
        self._fallback = fallback
        self._label = label
        self._is_active = False
        self._is_collapsed = False

        self.setCheckable(False)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(42)
        self.setIconSize(QSize(16, 16))

        self._update_style()
        self._update_content()

    def _update_content(self):
        c = AppConfig.COLORS
        color = c["accent"] if self._is_active else c["text_secondary"]
        ic = _icon(self._fa_name, color=color)
        if ic:
            self.setIcon(ic)
        if self._is_collapsed:
            self.setText("")
            self.setToolTip(self._label)
        else:
            if not ic:
                self.setText(f"  {self._fallback}  {self._label}")
            else:
                self.setText(f"  {self._label}")
            self.setToolTip("")

    def set_active(self, active: bool):
        self._is_active = active
        self._update_style()
        self._update_content()

    def set_collapsed(self, collapsed: bool):
        self._is_collapsed = collapsed
        self._update_content()

    def _update_style(self):
        c = AppConfig.COLORS
        if self._is_active:
            style = f"""
                QPushButton {{
                    background-color: {c['sidebar_item_active']};
                    color: {c['accent']};
                    border: none;
                    border-left: 3px solid {c['accent']};
                    text-align: left;
                    padding: 0 12px;
                    font-size: 12px;
                    font-weight: bold;
                }}
            """
        else:
            style = f"""
                QPushButton {{
                    background-color: transparent;
                    color: {c['text_secondary']};
                    border: none;
                    border-left: 3px solid transparent;
                    text-align: left;
                    padding: 0 12px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {c['sidebar_item_hover']};
                    color: {c['text_primary']};
                }}
            """
        self.setStyleSheet(style)


class Sidebar(QWidget):
    """Application sidebar with Font Awesome navigation icons."""

    page_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self._items: dict = {}
        self._is_collapsed = False
        self._active_page = None

        self.setFixedWidth(self.config.LAYOUT["sidebar_width"])
        self.setStyleSheet(f"background-color: {self.config.COLORS['bg_sidebar']};")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Brand header
        self.header = QWidget()
        self.header.setFixedHeight(50)
        self.header.setStyleSheet(f"""
            background-color: {self.config.COLORS['bg_sidebar']};
            border-bottom: 1px solid {self.config.COLORS['border']};
        """)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(14, 0, 14, 0)

        # Logo icon + text
        logo_ic = _icon("fa5s.microchip", color=self.config.COLORS["accent"], size=16)
        self.logo_icon_btn = QPushButton()
        self.logo_icon_btn.setFixedSize(22, 22)
        self.logo_icon_btn.setEnabled(False)
        self.logo_icon_btn.setStyleSheet("border: none; background: transparent;")
        self.logo_icon_btn.setIconSize(QSize(16, 16))
        if logo_ic:
            self.logo_icon_btn.setIcon(logo_ic)
        header_layout.addWidget(self.logo_icon_btn)

        self.logo_label = QLabel("MachineMonitor")
        self.logo_label.setStyleSheet(f"""
            color: {self.config.COLORS['accent']};
            font-size: 12px;
            font-weight: bold;
        """)
        header_layout.addWidget(self.logo_label)
        layout.addWidget(self.header)

        # Section label
        self.nav_label = QLabel("  NAVIGATION")
        self.nav_label.setFixedHeight(28)
        self.nav_label.setStyleSheet(f"""
            color: {self.config.COLORS['text_muted']};
            font-size: 7px;
            letter-spacing: 1px;
            font-weight: bold;
            padding-top: 8px;
        """)
        layout.addWidget(self.nav_label)

        # Nav items
        for fa_name, label, page_id, fallback in _NAV_DEFS:
            item = SidebarItem(fa_name, fallback, label, page_id)
            item.clicked.connect(lambda checked, pid=page_id: self.page_changed.emit(pid))
            self._items[page_id] = item
            layout.addWidget(item)

        layout.addStretch()

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {self.config.COLORS['border']};")
        layout.addWidget(sep)

        # Collapse button
        self.collapse_btn = QPushButton()
        self.collapse_btn.setFixedHeight(38)
        self.collapse_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.collapse_btn.setIconSize(QSize(14, 14))
        c_ic = _icon("fa5s.chevron-left", color=self.config.COLORS["text_muted"])
        if c_ic:
            self.collapse_btn.setIcon(c_ic)
            self.collapse_btn.setText("  Collapse")
        else:
            self.collapse_btn.setText("◀  Collapse")
        self.collapse_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.config.COLORS['text_muted']};
                border: none;
                text-align: left;
                padding: 0 14px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: {self.config.COLORS['text_primary']};
                background: {self.config.COLORS['sidebar_item_hover']};
            }}
        """)
        self.collapse_btn.clicked.connect(self.toggle_collapse)
        layout.addWidget(self.collapse_btn)

    def set_active(self, page_id: str):
        self._active_page = page_id
        for pid, item in self._items.items():
            item.set_active(pid == page_id)

    def toggle_collapse(self):
        self._is_collapsed = not self._is_collapsed
        expanded_w = self.config.LAYOUT["sidebar_width"]
        collapsed_w = self.config.LAYOUT["sidebar_collapsed_width"]
        c = self.config.COLORS

        if self._is_collapsed:
            self.setFixedWidth(collapsed_w)
            self.logo_label.hide()
            self.nav_label.hide()
            ic = _icon("fa5s.chevron-right", color=c["text_muted"])
            if ic:
                self.collapse_btn.setIcon(ic)
                self.collapse_btn.setText("")
            else:
                self.collapse_btn.setText("▶")
        else:
            self.setFixedWidth(expanded_w)
            self.logo_label.show()
            self.nav_label.show()
            ic = _icon("fa5s.chevron-left", color=c["text_muted"])
            if ic:
                self.collapse_btn.setIcon(ic)
                self.collapse_btn.setText("  Collapse")
            else:
                self.collapse_btn.setText("◀  Collapse")

        for item in self._items.values():
            item.set_collapsed(self._is_collapsed)
