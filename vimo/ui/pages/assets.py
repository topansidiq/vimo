"""
Assets page - CRUD for asset metadata.
"""

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from core.app_config import AppConfig
from core.data_manager import DataManager
from ui.widgets.cards import SectionHeader


class AssetsPage(QWidget):
    """CRUD page for assets."""

    COLUMNS = ["id", "name", "has_media", "path", "created_at", "updated_at"]

    def __init__(self, data_manager: DataManager, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self.data_manager = data_manager
        self._selected_asset_id = None
        self._dirty = True

        self._build_ui()
        self._connect_signals()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_if_needed)
        self._refresh_timer.start(500)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        root.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Assets")
        title.setStyleSheet(
            f"color: {self.config.COLORS['text_primary']}; font-size: 18px; font-weight: bold;"
        )
        layout.addWidget(title)

        subtitle = QLabel("CRUD data asset: id, name, has_media, path, timestamps")
        subtitle.setStyleSheet(
            f"color: {self.config.COLORS['text_muted']}; font-size: 10px;"
        )
        layout.addWidget(subtitle)

        layout.addWidget(SectionHeader("ASSET FORM"))
        form_group = self._make_group()
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.id_input = self._make_input("asset-001")
        self.name_input = self._make_input("Asset Name")
        self.path_input = self._make_input("/path/to/file")
        self.has_media_checkbox = QCheckBox("Has Media")
        self.has_media_checkbox.setStyleSheet(
            f"color: {self.config.COLORS['text_primary']}; font-size: 11px;"
        )

        self.created_at_label = QLabel("-")
        self.created_at_label.setStyleSheet(f"color: {self.config.COLORS['text_secondary']};")
        self.updated_at_label = QLabel("-")
        self.updated_at_label.setStyleSheet(f"color: {self.config.COLORS['text_secondary']};")

        form_layout.addRow("ID:", self.id_input)
        form_layout.addRow("Name:", self.name_input)
        form_layout.addRow("Path:", self.path_input)
        form_layout.addRow("Has Media:", self.has_media_checkbox)
        form_layout.addRow("Created At:", self.created_at_label)
        form_layout.addRow("Updated At:", self.updated_at_label)

        btn_row = QHBoxLayout()
        self.add_btn = self._make_btn("Add", accent=True)
        self.update_btn = self._make_btn("Update")
        self.delete_btn = self._make_btn("Delete")
        self.clear_btn = self._make_btn("Clear")

        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.update_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        form_layout.addRow("", btn_row)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"font-size: 10px; color: {self.config.COLORS['text_muted']};")
        form_layout.addRow("", self.status_label)

        layout.addWidget(form_group)

        layout.addWidget(SectionHeader("ASSET LIST"))
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Has Media", "Path", "Created At", "Updated At"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.table.setStyleSheet(self._table_style())
        self.table.setMinimumHeight(320)
        layout.addWidget(self.table)
        layout.addStretch()

    def _connect_signals(self):
        self.add_btn.clicked.connect(self._on_add)
        self.update_btn.clicked.connect(self._on_update)
        self.delete_btn.clicked.connect(self._on_delete)
        self.clear_btn.clicked.connect(self._on_clear)
        self.table.itemSelectionChanged.connect(self._on_table_selected)

        self.data_manager.assets_changed.connect(self._mark_dirty)

    def _mark_dirty(self):
        self._dirty = True

    def _refresh_if_needed(self):
        if not self._dirty:
            return
        self._dirty = False
        self._reload_table()

    def _reload_table(self):
        assets = self.data_manager.list_assets()
        current_selected = self._selected_asset_id

        self.table.setRowCount(len(assets))
        for row, asset in enumerate(assets):
            values = [
                asset.get("id", ""),
                asset.get("name", ""),
                "Yes" if asset.get("has_media", False) else "No",
                asset.get("path", ""),
                self._format_ts(asset.get("created_at")),
                self._format_ts(asset.get("updated_at")),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

        if current_selected:
            self._select_asset_row(current_selected)

    def _select_asset_row(self, asset_id: str):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.text() == asset_id:
                self.table.selectRow(row)
                break

    def _on_table_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return

        item = self.table.item(row, 0)
        if not item:
            return

        asset_id = item.text().strip()
        payload = self.data_manager.get_asset(asset_id)
        if not payload:
            return

        self._selected_asset_id = asset_id
        self.id_input.setText(payload.get("id", ""))
        self.name_input.setText(payload.get("name", ""))
        self.path_input.setText(payload.get("path", ""))
        self.has_media_checkbox.setChecked(bool(payload.get("has_media", False)))
        self.created_at_label.setText(self._format_ts(payload.get("created_at")))
        self.updated_at_label.setText(self._format_ts(payload.get("updated_at")))

    def _on_add(self):
        success, message = self.data_manager.create_asset(
            asset_id=self.id_input.text().strip(),
            name=self.name_input.text().strip(),
            has_media=self.has_media_checkbox.isChecked(),
            path=self.path_input.text().strip(),
        )
        self._flash_status(message, success)
        if success:
            self._selected_asset_id = self.id_input.text().strip()
            self._dirty = True

    def _on_update(self):
        current_id = self._selected_asset_id or self.id_input.text().strip()
        if not current_id:
            self._flash_status("Pilih asset dulu untuk update", False)
            return

        success, message = self.data_manager.update_asset(
            current_asset_id=current_id,
            new_asset_id=self.id_input.text().strip(),
            name=self.name_input.text().strip(),
            has_media=self.has_media_checkbox.isChecked(),
            path=self.path_input.text().strip(),
        )
        self._flash_status(message, success)
        if success:
            self._selected_asset_id = self.id_input.text().strip()
            self._dirty = True

    def _on_delete(self):
        current_id = self._selected_asset_id or self.id_input.text().strip()
        if not current_id:
            self._flash_status("Pilih asset dulu untuk dihapus", False)
            return

        answer = QMessageBox.question(
            self,
            "Delete Asset",
            f"Hapus asset '{current_id}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        success, message = self.data_manager.delete_asset(current_id)
        self._flash_status(message, success)
        if success:
            self._on_clear()
            self._dirty = True

    def _on_clear(self):
        self._selected_asset_id = None
        self.id_input.clear()
        self.name_input.clear()
        self.path_input.clear()
        self.has_media_checkbox.setChecked(False)
        self.created_at_label.setText("-")
        self.updated_at_label.setText("-")
        self.table.clearSelection()

    def _format_ts(self, value):
        if not value:
            return "-"
        try:
            from datetime import datetime

            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(value)

    def _flash_status(self, text: str, success: bool):
        color = self.config.COLORS["accent_success"] if success else self.config.COLORS["accent_danger"]
        self.status_label.setStyleSheet(f"font-size: 10px; color: {color};")
        self.status_label.setText(text)

    def _make_group(self):
        group = QGroupBox()
        group.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {self.config.COLORS['bg_card']};
                border: 1px solid {self.config.COLORS['border']};
                border-radius: {self.config.LAYOUT['card_radius']}px;
                padding: 12px;
                margin: 0;
            }}
            """
        )
        return group

    def _make_input(self, placeholder: str):
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setFixedHeight(30)
        inp.setStyleSheet(
            f"""
            QLineEdit {{
                background: {self.config.COLORS['bg_secondary']};
                color: {self.config.COLORS['text_primary']};
                border: 1px solid {self.config.COLORS['border']};
                border-radius: 4px;
                padding: 0 8px;
                font-size: 11px;
            }}
            QLineEdit:focus {{ border: 1px solid {self.config.COLORS['accent']}; }}
            """
        )
        return inp

    def _make_btn(self, label: str, accent: bool = False):
        btn = QPushButton(label)
        btn.setFixedHeight(30)
        btn.setCursor(Qt.PointingHandCursor)
        if accent:
            style = f"""
                QPushButton {{
                    background: {self.config.COLORS['accent']};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 0 14px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background: {self.config.COLORS['accent_hover']}; }}
            """
        else:
            style = f"""
                QPushButton {{
                    background: {self.config.COLORS['bg_secondary']};
                    color: {self.config.COLORS['text_secondary']};
                    border: 1px solid {self.config.COLORS['border']};
                    border-radius: 4px;
                    padding: 0 14px;
                }}
                QPushButton:hover {{
                    color: {self.config.COLORS['text_primary']};
                    background: {self.config.COLORS['bg_card_hover']};
                }}
            """
        btn.setStyleSheet(style)
        return btn

    def _table_style(self):
        c = self.config.COLORS
        return f"""
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
            QTableWidget::item:selected {{ background-color: {c['sidebar_item_active']}; }}
            QHeaderView::section {{
                background-color: {c['bg_secondary']};
                color: {c['text_secondary']};
                border: none;
                border-bottom: 1px solid {c['border']};
                padding: 4px 8px;
                font-size: 9px;
                font-weight: bold;
            }}
        """
