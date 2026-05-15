"""Floating reactive orb mini-mode launcher."""

from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QApplication, QWidget

from ui.animations import damp, pulse
from ui.theme import BLUE, CYAN, GREEN, VIOLET, WHITE, mono, with_alpha


class FloatingOrb(QWidget):
    """Always-on-top breathing mini interface."""

    request_expand = Signal()
    request_mic_toggle = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setFixedSize(104, 104)
        self.state = "boot"
        self._phase = 0.0
        self._last = time.perf_counter()
        self._hover = 0.0
        self._press_pos: QPoint | None = None
        self._drag_offset: QPoint | None = None
        self._dragging = False
        self._pop = 0.0
        self._target_pop = 0.0

        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - self.width() - 18, geo.bottom() - self.height() - 18)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_state(self, state: str) -> None:
        self.state = state
        self._target_pop = 1.0

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = min(0.05, now - self._last)
        self._last = now
        self._phase += dt
        self._pop = damp(self._pop, self._target_pop, 8.0, dt)
        self._target_pop = damp(self._target_pop, 0.0, 3.0, dt)
        self.update()

    def _state_color(self) -> QColor:
        return {
            "boot": VIOLET,
            "idle": BLUE,
            "listening": CYAN,
            "thinking": VIOLET,
            "speaking": GREEN,
        }.get(self.state, CYAN)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() * 0.5, self.height() * 0.5
        color = self._state_color()
        breath = pulse(self._phase * 0.62, 0.0, 1.0)
        active = 0.3 + 0.7 * (self.state in {"listening", "thinking", "speaking"})
        base = 30 + breath * 4 + self._hover * 5 + self._pop * 7

        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for i in range(6, 0, -1):
            radius = base + i * 7
            painter.setPen(Qt.NoPen)
            painter.setBrush(with_alpha(color, int(8 + active * 8 - i)))
            painter.drawEllipse(QPointF(cx, cy), radius, radius)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        for i in range(3):
            radius = base + 5 + i * 8
            painter.setPen(QPen(with_alpha(color, 112 - i * 28), 1.4))
            start = int((self._phase * (90 + i * 36) + i * 93) * 16)
            painter.drawArc(QRectF(cx - radius, cy - radius, radius * 2, radius * 2), start, int((150 - i * 22) * 16))

        grad = QRadialGradient(QPointF(cx - base * 0.25, cy - base * 0.28), base * 1.45)
        grad.setColorAt(0.0, QColor(245, 255, 255, 245))
        grad.setColorAt(0.26, with_alpha(WHITE, 220))
        grad.setColorAt(0.62, with_alpha(color, 235))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawEllipse(QPointF(cx, cy), base, base)

        painter.setFont(mono(9, True))
        painter.setPen(QPen(with_alpha(WHITE, 210), 1))
        painter.drawText(QRectF(cx - 32, cy - 8, 64, 18), Qt.AlignCenter, "JARVIS")
        painter.setFont(mono(6))
        painter.setPen(QPen(with_alpha(color, 210), 1))
        painter.drawText(QRectF(cx - 32, cy + 10, 64, 14), Qt.AlignCenter, self.state.upper()[:8])
        painter.end()

    def enterEvent(self, event) -> None:
        self._hover = 1.0
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = 0.0
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.LeftButton and self._drag_offset is not None:
            current = event.globalPosition().toPoint()
            if self._press_pos is not None and (current - self._press_pos).manhattanLength() > 5:
                self._dragging = True
            if self._dragging:
                self.move(current - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self._dragging:
            self.request_mic_toggle.emit()
        self._press_pos = None
        self._drag_offset = None
        self._dragging = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.request_expand.emit()
        super().mouseDoubleClickEvent(event)
