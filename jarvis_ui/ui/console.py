"""Reactive bottom command console with typewriter logs."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from ui.animations import clamp, damp, pulse
from ui.theme import CYAN, GREEN, MAGENTA, MUTED, PANEL_DARK, PANEL_DARKER, VIOLET, WHITE, mono, with_alpha


@dataclass
class ConsoleEntry:
    source: str
    text: str
    color: QColor
    stamp: str
    visible: int = 0
    age: float = 0.0


class ConsoleCanvas(QWidget):
    """Painted log stream with scanlines, typewriter reveal, and signal lanes."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(166)
        self.setMouseTracking(True)
        self.entries: list[ConsoleEntry] = []
        self._time = random.random() * 100
        self._last = time.perf_counter()
        self._audio = 0.0
        self._parallax_x = 0.0
        self._parallax_y = 0.0
        self._target_px = 0.0
        self._target_py = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_audio_level(self, level: float) -> None:
        self._audio = clamp(level, 0.0, 1.0)

    def set_parallax(self, parallax: QPointF) -> None:
        self._target_px = clamp(parallax.x(), -1.0, 1.0)
        self._target_py = clamp(parallax.y(), -1.0, 1.0)

    def add_entry(self, source: str, text: str, color: QColor) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.entries.append(ConsoleEntry(source, text, QColor(color), stamp))
        self.entries = self.entries[-32:]
        self.update()

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = min(0.05, now - self._last)
        self._last = now
        self._time += dt
        self._parallax_x = damp(self._parallax_x, self._target_px, 3.0, dt)
        self._parallax_y = damp(self._parallax_y, self._target_py, 3.0, dt)

        for entry in self.entries:
            entry.age += dt
            if entry.visible < len(entry.text):
                step = 2 if entry.source == "ai" else 3
                entry.visible = min(len(entry.text), entry.visible + step)
        self.update()

    def _panel_path(self, rect: QRectF) -> QPainterPath:
        cut = 18.0
        path = QPainterPath()
        path.moveTo(rect.left() + cut, rect.top())
        path.lineTo(rect.right() - cut, rect.top())
        path.lineTo(rect.right(), rect.top() + cut)
        path.lineTo(rect.right(), rect.bottom() - cut)
        path.lineTo(rect.right() - cut, rect.bottom())
        path.lineTo(rect.left() + cut, rect.bottom())
        path.lineTo(rect.left(), rect.bottom() - cut)
        path.lineTo(rect.left(), rect.top() + cut)
        path.closeSubpath()
        return path

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(4 + self._parallax_x * 5, 3 + self._parallax_y * 3, w - 8, h - 5)
        path = self._panel_path(rect)

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0, with_alpha(PANEL_DARK, 220))
        grad.setColorAt(0.58, with_alpha(PANEL_DARKER, 232))
        grad.setColorAt(1, QColor(4, 17, 34, 220))
        painter.fillPath(path, grad)
        painter.setPen(QPen(with_alpha(CYAN, int(72 + pulse(self._time * 0.5) * 34 + self._audio * 60)), 1.2))
        painter.drawPath(path)

        painter.save()
        painter.setClipPath(path)
        self._draw_background_signals(painter, rect)
        self._draw_entries(painter, rect)
        painter.restore()

        painter.setFont(mono(8, True))
        painter.setPen(QPen(with_alpha(CYAN, 220), 1))
        painter.drawText(QRectF(rect.left() + 16, rect.top() + 10, 190, 18), Qt.AlignLeft, "COMMAND STREAM")
        painter.setPen(QPen(with_alpha(CYAN, 48), 1))
        painter.drawLine(QPointF(rect.left() + 16, rect.top() + 34), QPointF(rect.right() - 16, rect.top() + 34))
        painter.end()

    def _draw_background_signals(self, painter: QPainter, rect: QRectF) -> None:
        for i in range(0, int(rect.height()), 7):
            alpha = int(5 + 8 * pulse(self._time * 0.7 + i * 0.01))
            painter.setPen(QPen(QColor(0, 165, 210, alpha), 1))
            y = rect.top() + i
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

        painter.setPen(QPen(with_alpha(CYAN, 42), 1))
        for lane in range(5):
            y = rect.top() + 48 + lane * 22
            start = rect.left() + ((self._time * (38 + lane * 8)) % rect.width())
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(QPen(with_alpha([CYAN, VIOLET, GREEN, MAGENTA, WHITE][lane % 5], 126), 2))
            painter.drawLine(QPointF(start, y), QPointF(min(start + 42, rect.right()), y))
            painter.setPen(QPen(with_alpha(CYAN, 42), 1))

    def _draw_entries(self, painter: QPainter, rect: QRectF) -> None:
        font = mono(9)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        line_height = metrics.height() + 6
        max_lines = max(1, int((rect.height() - 52) // line_height))
        visible_entries = self.entries[-max_lines:]
        y = rect.bottom() - 18 - (len(visible_entries) - 1) * line_height

        for entry in visible_entries:
            prefix_color = {
                "user": CYAN,
                "ai": GREEN,
                "system": VIOLET,
            }.get(entry.source, MUTED)
            prefix = {"user": "YOU", "ai": "JARVIS", "system": "SYS"}.get(entry.source, "LOG")
            shown = entry.text[: entry.visible]
            if entry.visible < len(entry.text) and int(self._time * 8) % 2 == 0:
                shown += "_"
            painter.setFont(mono(8))
            painter.setPen(QPen(with_alpha(MUTED, 120), 1))
            painter.drawText(QRectF(rect.left() + 18, y, 62, line_height), Qt.AlignVCenter | Qt.AlignLeft, entry.stamp)
            painter.setFont(mono(9, True))
            painter.setPen(QPen(with_alpha(prefix_color, 220), 1))
            painter.drawText(QRectF(rect.left() + 84, y, 64, line_height), Qt.AlignVCenter | Qt.AlignLeft, prefix)
            painter.setFont(font)
            painter.setPen(QPen(with_alpha(entry.color, 210), 1))
            text_rect = QRectF(rect.left() + 150, y, rect.width() - 172, line_height)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, metrics.elidedText(shown, Qt.ElideRight, int(text_rect.width())))
            y += line_height


class ReactiveConsole(QWidget):
    """Console frame plus command input, exposed as a single widget."""

    command_submitted = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(238)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.canvas = ConsoleCanvas(self)
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Enter command, or press Ctrl+M for voice reactor")
        self.input.returnPressed.connect(self._submit)
        self.input.setStyleSheet(
            """
            QLineEdit {
                background: rgba(2, 13, 31, 215);
                border: 1px solid rgba(0, 218, 255, 90);
                border-radius: 6px;
                color: rgb(225, 244, 255);
                selection-background-color: rgba(0, 218, 255, 80);
                padding: 8px 12px;
                font-family: Cascadia Mono, Consolas;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(42, 255, 167, 170);
                background: rgba(3, 20, 42, 235);
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.input)

    def set_audio_level(self, level: float) -> None:
        self.canvas.set_audio_level(level)

    def set_parallax(self, parallax: QPointF) -> None:
        self.canvas.set_parallax(parallax)

    def add_entry(self, source: str, text: str) -> None:
        color = {
            "user": WHITE,
            "ai": GREEN,
            "system": CYAN,
        }.get(source, MUTED)
        self.canvas.add_entry(source, text, color)

    def _submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.add_entry("user", text)
        self.command_submitted.emit(text)
