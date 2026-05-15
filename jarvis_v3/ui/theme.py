from PySide6.QtGui import QColor, QFont

class Theme:
    # Colors
    BG_DARK = "#050811"
    BG_PANEL = "#0a1122"
    BG_PANEL_TRANSPARENT = "rgba(10, 17, 34, 0.7)"
    BORDER = "#13233f"
    BORDER_GLOW = "#1d3864"
    ACCENT_CYAN = "#00d4ff"
    ACCENT_CYAN_DIM = "rgba(0, 212, 255, 0.2)"
    ACCENT_BLUE = "#0066ff"
    TEXT_WHITE = "#ffffff"
    TEXT_MUTED = "#6080a0"
    SUCCESS = "#00ff9d"
    SUCCESS_DIM = "rgba(0, 255, 157, 0.2)"
    
    # Fonts
    @staticmethod
    def get_font(size=10, bold=False, family="Segoe UI"):
        font = QFont(family, size)
        if bold:
            font.setBold(True)
        return font

    @staticmethod
    def get_title_font(size=14, family="Courier New"):
        font = QFont(family, size)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        return font

STYLESHEET = f"""
QWidget {{
    background-color: {Theme.BG_DARK};
    color: {Theme.TEXT_WHITE};
    font-family: 'Segoe UI', Arial, sans-serif;
}}

/* Common Panel Style */
.Panel {{
    background-color: {Theme.BG_PANEL};
    border: 1px solid {Theme.BORDER};
    border-radius: 12px;
}}

/* Buttons */
QPushButton {{
    background-color: transparent;
    border: 1px solid transparent;
    color: {Theme.TEXT_MUTED};
    text-align: left;
    padding: 10px 15px;
    border-radius: 8px;
    font-size: 13px;
}}

QPushButton:hover {{
    color: {Theme.ACCENT_CYAN};
    background-color: {Theme.ACCENT_CYAN_DIM};
    border: 1px solid {Theme.ACCENT_CYAN};
}}

QPushButton:checked {{
    color: {Theme.ACCENT_CYAN};
    background-color: {Theme.ACCENT_CYAN_DIM};
    border-left: 3px solid {Theme.ACCENT_CYAN};
}}

/* Progress Bars */
QProgressBar {{
    background-color: {Theme.BG_DARK};
    border: 1px solid {Theme.BORDER};
    border-radius: 4px;
    text-align: right;
    color: {Theme.ACCENT_CYAN};
    font-size: 10px;
}}

QProgressBar::chunk {{
    background-color: {Theme.ACCENT_CYAN};
    border-radius: 3px;
}}

/* Labels */
QLabel {{
    background: transparent;
}}

/* Scrollbars */
QScrollBar:vertical {{
    border: none;
    background: {Theme.BG_DARK};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {Theme.BORDER};
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {Theme.ACCENT_CYAN};
}}
"""
