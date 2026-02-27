"""
Application configuration including theme, colors, and stylesheet.
"""


class AppConfig:
    """Centralized application configuration."""

    # Color Palette - Dark Gray Theme
    COLORS = {
        "bg_primary": "#1a1a1a",
        "bg_secondary": "#242424",
        "bg_sidebar": "#1e1e1e",
        "bg_card": "#2a2a2a",
        "bg_card_hover": "#303030",
        "bg_topbar": "#1c1c1c",
        "bg_menubar": "#1c1c1c",
        "accent": "#4a9eff",
        "accent_hover": "#5aaeFF",
        "accent_success": "#4caf50",
        "accent_warning": "#ff9800",
        "accent_danger": "#f44336",
        "accent_info": "#2196f3",
        "text_primary": "#e0e0e0",
        "text_secondary": "#9e9e9e",
        "text_muted": "#616161",
        "border": "#333333",
        "border_light": "#3d3d3d",
        "sidebar_item_hover": "#2c2c2c",
        "sidebar_item_active": "#2d3f5e",
        "chart_bg": "#1e1e1e",
        "scrollbar": "#3a3a3a",
        "scrollbar_hover": "#4a4a4a",
    }

    # Font settings
    FONTS = {
        "family": "Segoe UI",
        "family_fallback": "Arial",
        "size_xs": 9,
        "size_sm": 10,
        "size_base": 11,
        "size_md": 12,
        "size_lg": 14,
        "size_xl": 16,
        "size_2xl": 20,
        "size_3xl": 24,
    }

    # Layout dimensions
    LAYOUT = {
        "sidebar_width": 220,
        "sidebar_collapsed_width": 60,
        "topbar_height": 40,
        "menubar_height": 24,
        "card_radius": 6,
        "padding": 16,
    }

    # Window settings
    WINDOW = {
        "min_width": 1200,
        "min_height": 700,
        "default_width": 1400,
        "default_height": 850,
        "title": "Machine Monitor v1.0",
    }

    def get_stylesheet(self) -> str:
        """Return the complete application stylesheet."""
        c = self.COLORS
        f = self.FONTS

        return f"""
        /* ===== GLOBAL ===== */
        QWidget {{
            background-color: {c['bg_primary']};
            color: {c['text_primary']};
            font-family: '{f['family']}', '{f['family_fallback']}', sans-serif;
            font-size: {f['size_base']}px;
        }}

        /* ===== MENU BAR ===== */
        QMenuBar {{
            background-color: {c['bg_menubar']};
            color: {c['text_primary']};
            border-bottom: 1px solid {c['border']};
            padding: 2px 4px;
            font-size: {f['size_sm']}px;
        }}
        QMenuBar::item {{
            padding: 4px 10px;
            border-radius: 3px;
        }}
        QMenuBar::item:selected, QMenuBar::item:pressed {{
            background-color: {c['accent']};
            color: #ffffff;
        }}
        QMenu {{
            background-color: {c['bg_secondary']};
            border: 1px solid {c['border']};
            border-radius: 4px;
            padding: 4px 0px;
        }}
        QMenu::item {{
            padding: 6px 20px 6px 12px;
            font-size: {f['size_sm']}px;
        }}
        QMenu::item:selected {{
            background-color: {c['accent']};
            color: #ffffff;
        }}
        QMenu::separator {{
            height: 1px;
            background: {c['border']};
            margin: 4px 0px;
        }}

        /* ===== SCROLL BARS ===== */
        QScrollBar:vertical {{
            background: {c['bg_primary']};
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {c['scrollbar']};
            border-radius: 4px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {c['scrollbar_hover']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: {c['bg_primary']};
            height: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: {c['scrollbar']};
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {c['scrollbar_hover']};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* ===== TOOLTIPS ===== */
        QToolTip {{
            background-color: {c['bg_card']};
            color: {c['text_primary']};
            border: 1px solid {c['border']};
            padding: 4px 8px;
            border-radius: 4px;
        }}

        /* ===== SPLITTER ===== */
        QSplitter::handle {{
            background: {c['border']};
        }}

        /* ===== STATUS BAR ===== */
        QStatusBar {{
            background-color: {c['bg_menubar']};
            color: {c['text_secondary']};
            border-top: 1px solid {c['border']};
            font-size: {f['size_xs']}px;
        }}
        """
