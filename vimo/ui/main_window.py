"""
Main Application Window.
Assembles the menu bar, sidebar, and content area.
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QAction, QStatusBar, QLabel, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QIcon, QFont

from core.app_config import AppConfig
from core.data_manager import DataManager
from ui.widgets.sidebar import Sidebar
from ui.widgets.topbar import TopBar
from ui.pages.dashboard import DashboardPage
from ui.pages.settings import SettingsPage
from ui.pages.activity import ActivityPage
from ui.pages.log_statistic import LogStatisticPage
from ui.pages.devices import DevicesPage
from ui.pages.assets import AssetsPage


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.config = AppConfig()
        self.data_manager = DataManager(self)

        self._setup_window()
        self._setup_data_manager()
        self._build_ui()
        self._setup_menubar()
        self._setup_statusbar()
        self._connect_signals()
        # Wire fullscreen button in topbar
        self.topbar.fullscreen_requested.connect(self._toggle_fullscreen)

        # Navigate to dashboard by default
        self.navigate_to("dashboard")

    def _setup_window(self):
        cfg = self.config.WINDOW
        self.setWindowTitle(cfg["title"])
        self.setMinimumSize(cfg["min_width"], cfg["min_height"])
        self.resize(cfg["default_width"], cfg["default_height"])

    def _setup_data_manager(self):
        self.data_manager.connection_status_changed.connect(self._on_connection_changed)
        self.data_manager.alert_triggered.connect(self._on_alert)

    def _build_ui(self):
        """Build the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Top bar
        self.topbar = TopBar(self.data_manager)
        root_layout.addWidget(self.topbar)

        # Content area (sidebar + pages)
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        root_layout.addWidget(content_widget)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.page_changed.connect(self.navigate_to)
        content_layout.addWidget(self.sidebar)

        # Vertical separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet(f"color: {self.config.COLORS['border']};")
        content_layout.addWidget(separator)

        # Pages container
        self.pages_widget = QWidget()
        self.pages_layout = QVBoxLayout(self.pages_widget)
        self.pages_layout.setContentsMargins(0, 0, 0, 0)
        self.pages_layout.setSpacing(0)
        content_layout.addWidget(self.pages_widget, 1)

        # Initialize pages
        self._pages = {}
        self._init_pages()

    def _init_pages(self):
        """Create and register all pages."""
        pages = {
            "dashboard": DashboardPage(self.data_manager),
            "activity": ActivityPage(self.data_manager),
            "settings": SettingsPage(self.data_manager),
            "log_statistic": LogStatisticPage(self.data_manager),
            "devices": DevicesPage(self.data_manager),
            "assets": AssetsPage(self.data_manager),
        }

        for name, page in pages.items():
            self._pages[name] = page
            self.pages_layout.addWidget(page)
            page.hide()

    def _setup_menubar(self):
        """Build the application menu bar."""
        menubar = self.menuBar()
        menubar.setStyleSheet(f"""
            QMenuBar {{
                background-color: {self.config.COLORS['bg_menubar']};
                border-bottom: 1px solid {self.config.COLORS['border']};
            }}
        """)

        # File Menu
        file_menu = menubar.addMenu("&File")
        self._add_action(file_menu, "Connect to Server...", "Ctrl+Shift+C", self._on_connect)
        self._add_action(file_menu, "Disconnect", None, self._on_disconnect)
        file_menu.addSeparator()
        self._add_action(file_menu, "Export Data...", "Ctrl+E", self._on_export)
        self._add_action(file_menu, "Export Logs...", None, self._on_export_logs)
        file_menu.addSeparator()
        self._add_action(file_menu, "Exit", "Alt+F4", self.close)

        # View Menu
        view_menu = menubar.addMenu("&View")
        self._add_action(view_menu, "Dashboard", "Ctrl+1", lambda: self.navigate_to("dashboard"))
        self._add_action(view_menu, "Activity", "Ctrl+2", lambda: self.navigate_to("activity"))
        self._add_action(view_menu, "Log & Statistics", "Ctrl+3", lambda: self.navigate_to("log_statistic"))
        self._add_action(view_menu, "Devices", "Ctrl+4", lambda: self.navigate_to("devices"))
        self._add_action(view_menu, "Assets", "Ctrl+5", lambda: self.navigate_to("assets"))
        view_menu.addSeparator()
        self._add_action(view_menu, "Toggle Sidebar", "Ctrl+B", self.sidebar.toggle_collapse)
        view_menu.addSeparator()
        self._add_action(view_menu, "Full Screen", "F11", self._toggle_fullscreen)

        # Configure Menu
        configure_menu = menubar.addMenu("&Configure")
        self._add_action(configure_menu, "Settings", "Ctrl+,", lambda: self.navigate_to("settings"))
        configure_menu.addSeparator()
        self._add_action(configure_menu, "Manage Devices...", None, self._on_manage_machines)
        self._add_action(configure_menu, "Manage Assets...", None, lambda: self.navigate_to("assets"))
        self._add_action(configure_menu, "Alert Thresholds...", None, self._on_alert_thresholds)
        self._add_action(configure_menu, "Data Sources...", None, self._on_data_sources)

        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")
        self._add_action(tools_menu, "Clear All Data", None, self._on_clear_data)
        tools_menu.addSeparator()
        self._add_action(tools_menu, "Diagnostic Report", None, self._on_diagnostic)
        self._add_action(tools_menu, "About Machine Monitor", None, self._on_about)

    def _add_action(self, menu, text: str, shortcut: str, slot):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _setup_statusbar(self):
        """Set up the status bar."""
        self.status_bar = self.statusBar()
        self.status_bar.setFixedHeight(22)

        # Connection status
        self.status_connection = QLabel("● Disconnected")
        self.status_connection.setStyleSheet("color: #9e9e9e; padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.status_connection)

        # Data rate
        self.status_rate = QLabel("Rate: 0 Hz")
        self.status_rate.setStyleSheet("color: #9e9e9e; padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.status_rate)

        # Clock
        self.status_clock = QLabel()
        self.status_clock.setStyleSheet("color: #9e9e9e; padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.status_clock)

        # Clock timer
        clock_timer = QTimer(self)
        clock_timer.timeout.connect(self._update_clock)
        clock_timer.start(1000)
        self._update_clock()

        # Rate counter
        self._rate_count = 0
        self._rate_timer = QTimer(self)
        self._rate_timer.timeout.connect(self._update_rate)
        self._rate_timer.start(1000)
        self.data_manager.data_updated.connect(lambda *_: self._increment_rate())

    def _connect_signals(self):
        pass

    # ── Navigation ────────────────────────────────────────────────────────────

    def navigate_to(self, page_name: str):
        """Navigate to a named page."""
        for name, page in self._pages.items():
            if name == page_name:
                page.show()
            else:
                page.hide()
        self.sidebar.set_active(page_name)
        title_map = {
            "dashboard": "Dashboard",
            "activity": "Activity",
            "log_statistic": "Log & Statistics",
            "devices": "Devices",
            "assets": "Assets",
            "settings": "Settings",
        }
        self.topbar.set_title(title_map.get(page_name, "Machine Monitor"))

    # ── Slots ─────────────────────────────────────────────────────────────────

    @pyqtSlot(bool)
    def _on_connection_changed(self, connected: bool):
        if connected:
            self.status_connection.setText("● Connected")
            self.status_connection.setStyleSheet("color: #4caf50; padding: 0 10px;")
            self.status_bar.showMessage("Connection established", 3000)
        else:
            self.status_connection.setText("● Disconnected")
            self.status_connection.setStyleSheet("color: #9e9e9e; padding: 0 10px;")

    @pyqtSlot(str, str, str)
    def _on_alert(self, machine_id: str, level: str, message: str):
        color = "#ff9800" if level == "Warning" else "#f44336"
        self.status_bar.showMessage(
            f"[{level.upper()}] {machine_id}: {message}", 5000
        )

    def _update_clock(self):
        from datetime import datetime
        self.status_clock.setText(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))

    def _increment_rate(self):
        self._rate_count += 1

    def _update_rate(self):
        self.status_rate.setText(f"Rate: {self._rate_count} Hz")
        self._rate_count = 0

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.topbar.update_fullscreen_icon(False)
        else:
            self.showFullScreen()
            self.topbar.update_fullscreen_icon(True)

    # Placeholder menu handlers
    def _on_connect(self):
        self.navigate_to("settings")
        self.status_bar.showMessage("Configure connection in Settings", 3000)

    def _on_disconnect(self):
        self.data_manager.disconnect_server()

    def _on_export(self):
        self.status_bar.showMessage("Export Data - feature coming soon", 3000)

    def _on_export_logs(self):
        self.status_bar.showMessage("Export Logs - feature coming soon", 3000)

    def _on_manage_machines(self):
        self.navigate_to("devices")

    def _on_alert_thresholds(self):
        self.navigate_to("settings")

    def _on_data_sources(self):
        self.navigate_to("settings")

    def _on_clear_data(self):
        self.data_manager.clear_all_data()
        self.status_bar.showMessage("Data cleared", 2000)

    def _on_diagnostic(self):
        self.navigate_to("log_statistic")

    def _on_about(self):
        from PyQt5.QtWidgets import QMessageBox
        from core.app_config import APP_VERSION
        QMessageBox.about(
            self, "About Machine Monitor",
            f"<b>Machine Monitor v{APP_VERSION}</b><br><br>"
            "Enterprise Real-Time Machine Monitoring<br>"
            "MPU6050 Accelerometer / Gyroscope<br><br>"
            "Built with Python + PyQt5"
        )

    def closeEvent(self, event):
        self.data_manager.disconnect_server()
        event.accept()
