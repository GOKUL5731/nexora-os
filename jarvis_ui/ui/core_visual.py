"""Animated central AI core rendered with QPainter."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QConicalGradient, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from ui.animations import TAU, clamp, damp, ease_out_cubic, pulse, rotate_point
from ui.theme import BLUE, CYAN, GREEN, MAGENTA, MUTED, VIOLET, WHITE, mono, ui_font, with_alpha


@dataclass
class RingSpec:
    radius: float
    width: float
    color: QColor
    speed: float
    span: float
    offset: float
    alpha: int


@dataclass
class SurfacePulse:
    age: float
    strength: float


class AICoreWidget(QWidget):
    """Dominant reactor-like visual centerpiece."""

    clicked = Signal(QPointF)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(520, 520)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.state = "boot"
        self._state_intensity = 0.0
        self._target_intensity = 0.18
        self._audio = 0.0
        self._audio_smoothed = 0.0
        self._hover = 0.0
        self._phase = random.random() * 20.0
        self._last = time.perf_counter()
        self._angle_a = 0.0
        self._angle_b = 180.0
        self._angle_c = 65.0
        self._parallax_x = 0.0
        self._parallax_y = 0.0
        self._target_px = 0.0
        self._target_py = 0.0
        self._wave = [0.0 for _ in range(96)]
        self._pulses: list[SurfacePulse] = []
        self._micro_nodes = [
            (random.random() * TAU, random.uniform(0.28, 0.94), random.uniform(0.7, 1.4))
            for _ in range(42)
        ]

        self._rings = [
            RingSpec(0.45, 2.2, CYAN, 28.0, 250.0, 0.0, 180),
            RingSpec(0.54, 1.3, VIOLET, -16.0, 210.0, 70.0, 130),
            RingSpec(0.64, 2.0, BLUE, 10.0, 300.0, 160.0, 112),
            RingSpec(0.74, 1.0, GREEN, -7.0, 170.0, 225.0, 96),
            RingSpec(0.84, 1.0, CYAN, 5.0, 118.0, 310.0, 74),
        ]

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_state(self, state: str) -> None:
        self.state = state
        self._target_intensity = {
            "boot": 0.64,
            "idle": 0.22,
            "listening": 0.70,
            "thinking": 0.88,
            "speaking": 1.0,
        }.get(state, 0.28)
        if state in {"thinking", "speaking"}:
            self.trigger_surface_pulse(0.9)

    def set_audio_level(self, level: float) -> None:
        self._audio = clamp(level, 0.0, 1.0)

    def set_parallax(self, parallax: QPointF) -> None:
        self._target_px = clamp(parallax.x(), -1.0, 1.0)
        self._target_py = clamp(parallax.y(), -1.0, 1.0)

    def trigger_surface_pulse(self, strength: float = 0.65) -> None:
        self._pulses.append(SurfacePulse(0.0, strength))
        self._pulses = self._pulses[-6:]

    def enterEvent(self, event) -> None:
        self._hover = 1.0
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = 0.0
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.trigger_surface_pulse(0.8)
            self.clicked.emit(event.position())
        super().mousePressEvent(event)

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = min(0.05, now - self._last)
        self._last = now

        self._phase += dt
        self._state_intensity = damp(self._state_intensity, self._target_intensity, 4.0, dt)
        self._audio_smoothed = damp(self._audio_smoothed, self._audio, 14.0, dt)
        self._parallax_x = damp(self._parallax_x, self._target_px, 4.0, dt)
        self._parallax_y = damp(self._parallax_y, self._target_py, 4.0, dt)

        speed = 0.65 + self._state_intensity * 1.55 + self._audio_smoothed * 1.25
        self._angle_a = (self._angle_a + 26.0 * dt * speed) % 360
        self._angle_b = (self._angle_b - 17.0 * dt * speed) % 360
        self._angle_c = (self._angle_c + 38.0 * dt * (0.75 + self._audio_smoothed)) % 360

        for i, value in enumerate(self._wave):
            voice = math.sin(self._phase * 10.0 + i * 0.36) * self._audio_smoothed
            carrier = math.sin(self._phase * 2.0 + i * 0.14) * self._state_intensity * 0.25
            target = (voice + carrier + random.uniform(-0.025, 0.025)) * 26.0
            self._wave[i] = damp(value, target, 12.0, dt)

        for pulse_item in self._pulses:
            pulse_item.age += dt
        self._pulses = [item for item in self._pulses if item.age < 1.5]
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        cx = w * 0.5 + self._parallax_x * 9.0
        cy = h * 0.50 + self._parallax_y * 8.0
        radius = min(w, h) * 0.43

        self._draw_depth_particles(painter, cx, cy, radius)
        self._draw_emission_waves(painter, cx, cy, radius)
        self._draw_outer_field(painter, cx, cy, radius)
        self._draw_rotating_rings(painter, cx, cy, radius)
        self._draw_radial_ticks(painter, cx, cy, radius)
        self._draw_orbiting_nodes(painter, cx, cy, radius)
        self._draw_waveform(painter, cx, cy, radius)
        self._draw_core_orb(painter, cx, cy, radius)
        self._draw_labels(painter, cx, cy, radius)

        painter.end()

    def _state_color(self) -> QColor:
        return {
            "boot": VIOLET,
            "idle": CYAN,
            "listening": CYAN,
            "thinking": VIOLET,
            "speaking": GREEN,
        }.get(self.state, CYAN)

    def _draw_depth_particles(self, painter: QPainter, cx: float, cy: float, radius: float) -> None:
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for angle, depth, speed in self._micro_nodes:
            phase = angle + self._phase * speed * 0.18
            wobble = math.sin(self._phase * speed + angle) * radius * 0.035
            r = radius * (0.34 + depth * 0.66) + wobble
            x = cx + math.cos(phase) * r + self._parallax_x * depth * 14.0
            y = cy + math.sin(phase) * r * 0.82 + self._parallax_y * depth * 10.0
            alpha = int(18 + depth * 72 + self._audio_smoothed * 38)
            painter.setPen(Qt.NoPen)
            painter.setBrush(with_alpha(CYAN, alpha))
            size = 0.9 + depth * 2.0
            painter.drawEllipse(QPointF(x, y), size, size)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

    def _draw_emission_waves(self, painter: QPainter, cx: float, cy: float, radius: float) -> None:
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        color = self._state_color()
        for item in self._pulses:
            t = item.age / 1.5
            alpha = int((1.0 - t) * 120 * item.strength)
            r = radius * (0.20 + ease_out_cubic(t) * 1.07)
            painter.setPen(QPen(with_alpha(color, alpha), 1.6))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), r, r * 0.86)
        for i in range(3):
            phase = (self._phase * 0.18 + i / 3.0) % 1.0
            alpha = int((1.0 - phase) * (26 + self._audio_smoothed * 40))
            r = radius * (0.32 + phase * 0.92)
            painter.setPen(QPen(with_alpha(CYAN, alpha), 1.0))
            painter.drawEllipse(QPointF(cx, cy), r, r)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

    def _draw_outer_field(self, painter: QPainter, cx: float, cy: float, radius: float) -> None:
        color = self._state_color()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for i in range(9, 0, -1):
            r = radius * (0.14 + i * 0.085) * (1.0 + self._audio_smoothed * 0.045)
            alpha = int((10 - i) * 4 + self._state_intensity * 12)
            painter.setPen(QPen(with_alpha(color, alpha), 2.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), r, r)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        conic = QConicalGradient(QPointF(cx, cy), -self._angle_c)
        conic.setColorAt(0.0, with_alpha(color, 0))
        conic.setColorAt(0.10, with_alpha(color, 42))
        conic.setColorAt(0.16, with_alpha(WHITE, 72))
        conic.setColorAt(0.20, with_alpha(color, 0))
        conic.setColorAt(1.0, with_alpha(color, 0))
        painter.setBrush(conic)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), radius * 0.79, radius * 0.79)

    def _draw_rotating_rings(self, painter: QPainter, cx: float, cy: float, radius: float) -> None:
        activity = 1.0 + self._state_intensity * 0.48 + self._audio_smoothed * 0.30
        painter.setBrush(Qt.NoBrush)
        for spec in self._rings:
            r = radius * spec.radius * (1.0 + self._audio_smoothed * 0.025)
            angle = (spec.offset + self._angle_a * spec.speed / 28.0 * activity) % 360
            color = QColor(spec.color)
            color.setAlpha(int(clamp(spec.alpha + self._audio_smoothed * 60, 0, 255)))
            pen = QPen(color, spec.width)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            rect = QRectF(cx - r, cy - r, r * 2.0, r * 2.0)
            painter.drawArc(rect, int(angle * 16), int(spec.span * 16))
            painter.drawArc(rect, int((angle + spec.span + 28.0) * 16), int(42 * 16))

        painter.setPen(QPen(with_alpha(VIOLET, 95), 1.0))
        for i in range(4):
            r = radius * (0.28 + i * 0.12)
            rect = QRectF(cx - r, cy - r, r * 2, r * 2)
            painter.drawArc(rect, int((-self._angle_b + i * 31) * 16), int((72 + i * 16) * 16))

    def _draw_radial_ticks(self, painter: QPainter, cx: float, cy: float, radius: float) -> None:
        for deg in range(0, 360, 4):
            major = deg % 30 == 0
            medium = deg % 10 == 0
            inner = radius * (0.87 if major else 0.905 if medium else 0.925)
            outer = radius * 0.955
            alpha = 112 if major else 78 if medium else 42
            if abs(((deg - self._angle_c + 540) % 360) - 180) < 14:
                alpha += 80
            painter.setPen(QPen(with_alpha(CYAN, clamp(alpha + self._audio_smoothed * 42, 0, 255)), 1.2 if major else 0.8))
            x1, y1 = rotate_point(cx, cy, inner, deg)
            x2, y2 = rotate_point(cx, cy, outer, deg)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _draw_orbiting_nodes(self, painter: QPainter, cx: float, cy: float, radius: float) -> None:
        colors = [CYAN, GREEN, VIOLET, MAGENTA]
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for i in range(12):
            lane = 0.47 + (i % 4) * 0.105
            angle = self._angle_a * (0.55 + i * 0.015) + i * 31.5
            x, y = rotate_point(cx, cy, radius * lane, angle)
            color = colors[i % len(colors)]
            painter.setPen(Qt.NoPen)
            painter.setBrush(with_alpha(color, 160))
            size = 3.0 + (i % 3) + self._audio_smoothed * 2.0
            painter.drawEllipse(QPointF(x, y), size, size)
            painter.setBrush(with_alpha(color, 32))
            painter.drawEllipse(QPointF(x, y), size * 4.0, size * 4.0)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

    def _draw_waveform(self, painter: QPainter, cx: float, cy: float, radius: float) -> None:
        base_r = radius * 0.34
        path = QPainterPath()
        for i, amp in enumerate(self._wave):
            angle = (i / len(self._wave)) * TAU
            r = base_r + amp
            x = cx + math.cos(angle) * r
            y = cy + math.sin(angle) * r
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        pen = QPen(with_alpha(WHITE, int(48 + self._audio_smoothed * 118)), 1.2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def _draw_core_orb(self, painter: QPainter, cx: float, cy: float, radius: float) -> None:
        color = self._state_color()
        core_radius = radius * (0.128 + self._state_intensity * 0.018 + self._audio_smoothed * 0.035)
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for i in range(8, 0, -1):
            r = core_radius * (1.0 + i * 0.42)
            painter.setPen(Qt.NoPen)
            painter.setBrush(with_alpha(color, max(4, 35 - i * 3)))
            painter.drawEllipse(QPointF(cx, cy), r, r)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        grad = QRadialGradient(QPointF(cx - core_radius * 0.25, cy - core_radius * 0.28), core_radius * 1.45)
        grad.setColorAt(0.0, QColor(248, 255, 255, 255))
        grad.setColorAt(0.22, with_alpha(WHITE, 230))
        grad.setColorAt(0.50, with_alpha(color, 230))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawEllipse(QPointF(cx, cy), core_radius, core_radius)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(with_alpha(WHITE, 130), 1.0))
        painter.drawEllipse(QPointF(cx, cy), core_radius * 0.58, core_radius * 0.58)
        painter.setPen(QPen(with_alpha(CYAN, 150), 1.1))
        painter.drawArc(
            QRectF(cx - core_radius * 1.22, cy - core_radius * 1.22, core_radius * 2.44, core_radius * 2.44),
            int(self._angle_b * 16),
            int(150 * 16),
        )

    def _draw_labels(self, painter: QPainter, cx: float, cy: float, radius: float) -> None:
        state_label = {
            "boot": "BOOTING",
            "idle": "STANDBY",
            "listening": "LISTENING",
            "thinking": "PROCESSING",
            "speaking": "SPEAKING",
        }.get(self.state, "ONLINE")
        painter.setFont(ui_font(18, True))
        painter.setPen(QPen(with_alpha(WHITE, 210), 1))
        painter.drawText(QRectF(cx - 125, cy - radius * 0.075, 250, 34), Qt.AlignCenter, "JARVIS")
        painter.setFont(mono(9, True))
        painter.setPen(QPen(with_alpha(self._state_color(), 210), 1))
        painter.drawText(QRectF(cx - 150, cy + radius * 0.095, 300, 24), Qt.AlignCenter, state_label)

        painter.setPen(QPen(with_alpha(MUTED, 150), 1))
        painter.setFont(mono(8))
        painter.drawText(QRectF(cx - 95, cy + radius * 0.205, 190, 20), Qt.AlignCenter, "SIGNAL CORE")
