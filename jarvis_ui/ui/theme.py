"""Shared visual tokens for the cinematic command interface."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont


BG_DEEP = QColor(2, 5, 15)
BG_MID = QColor(4, 13, 30)
PANEL_DARK = QColor(4, 16, 34, 205)
PANEL_DARKER = QColor(1, 8, 20, 230)

CYAN = QColor(0, 218, 255)
CYAN_SOFT = QColor(78, 214, 255)
BLUE = QColor(35, 94, 255)
DEEP_BLUE = QColor(14, 36, 105)
VIOLET = QColor(155, 90, 255)
MAGENTA = QColor(255, 78, 205)
GREEN = QColor(42, 255, 167)
AMBER = QColor(255, 186, 70)
RED = QColor(255, 76, 112)
WHITE = QColor(225, 244, 255)
MUTED = QColor(92, 132, 170)
LINE_DIM = QColor(36, 132, 190, 72)

FONT_UI = "Segoe UI"
FONT_MONO = "Cascadia Mono"
FONT_MONO_FALLBACK = "Consolas"


def mono(size: int = 10, bold: bool = False) -> QFont:
    font = QFont(FONT_MONO, size)
    if not font.exactMatch():
        font = QFont(FONT_MONO_FALLBACK, size)
    font.setBold(bold)
    return font


def ui_font(size: int = 10, bold: bool = False) -> QFont:
    font = QFont(FONT_UI, size)
    font.setBold(bold)
    return font


def with_alpha(color: QColor, alpha: int | float) -> QColor:
    out = QColor(color)
    if isinstance(alpha, float):
        out.setAlphaF(max(0.0, min(1.0, alpha)))
    else:
        out.setAlpha(max(0, min(255, alpha)))
    return out
