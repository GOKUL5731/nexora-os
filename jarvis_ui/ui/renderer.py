"""OpenGL-backed cinematic background renderer."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from ui.animations import TAU, clamp, damp, ease_out_cubic, pulse
from ui.theme import BG_DEEP, BG_MID, BLUE, CYAN, GREEN, LINE_DIM, MAGENTA, VIOLET, WHITE, with_alpha


@dataclass
class FieldParticle:
    x: float
    y: float
    z: float
    vx: float
    vy: float
    phase: float
    size: float


@dataclass
class Ripple:
    x: float
    y: float
    age: float
    strength: float


@dataclass
class Packet:
    route: int
    t: float
    speed: float
    hue: int


class CinematicRenderer(QOpenGLWidget):
    """GPU-composited particle field, parallax grid, signal routes, and pulses."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setMouseTracking(True)
        self._particles: list[FieldParticle] = []
        self._ripples: list[Ripple] = []
        self._packets: list[Packet] = []
        self._routes: list[tuple[QPointF, QPointF, QPointF]] = []
        self._last = time.perf_counter()
        self._time = random.random() * 100.0
        self._audio_level = 0.0
        self._state = "idle"
        self._parallax_x = 0.0
        self._parallax_y = 0.0
        self._target_px = 0.0
        self._target_py = 0.0
        self._rects: dict[str, QRect] = {}

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def initializeGL(self) -> None:
        # Qt paints this widget through an OpenGL framebuffer; QPainter work below
        # gets GPU-composited while keeping the code portable across Windows GPUs.
        pass

    def resizeGL(self, width: int, height: int) -> None:
        self._seed_particles(width, height)
        self._seed_packets()

    def set_state(self, state: str) -> None:
        self._state = state

    def set_audio_level(self, level: float) -> None:
        self._audio_level = clamp(level, 0.0, 1.0)

    def set_parallax(self, parallax: QPointF) -> None:
        self._target_px = clamp(parallax.x(), -1.0, 1.0)
        self._target_py = clamp(parallax.y(), -1.0, 1.0)

    def set_interface_geometry(self, **rects: QRect) -> None:
        self._rects = {name: QRect(rect) for name, rect in rects.items()}
        self._build_routes()

    def add_ripple(self, pos: QPointF, strength: float = 0.6) -> None:
        self._ripples.append(Ripple(pos.x(), pos.y(), 0.0, strength))
        self._ripples = self._ripples[-8:]

    def _seed_particles(self, width: int, height: int) -> None:
        count = max(120, min(260, (width * height) // 8200))
        self._particles = [
            FieldParticle(
                random.random() * max(width, 1),
                random.random() * max(height, 1),
                random.uniform(0.12, 1.0),
                random.uniform(-10.0, 10.0),
                random.uniform(-18.0, 8.0),
                random.random(),
                random.uniform(0.8, 2.5),
            )
            for _ in range(count)
        ]

    def _seed_packets(self) -> None:
        if self._packets:
            return
        self._packets = [
            Packet(i % 8, random.random(), random.uniform(0.10, 0.27), random.randrange(0, 4))
            for i in range(26)
        ]

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = min(0.05, now - self._last)
        self._last = now
        self._time += dt
        self._parallax_x = damp(self._parallax_x, self._target_px, 4.5, dt)
        self._parallax_y = damp(self._parallax_y, self._target_py, 4.5, dt)

        w, h = max(self.width(), 1), max(self.height(), 1)
        for particle in self._particles:
            drift = 1.0 + particle.z * 1.8 + self._audio_level * 0.8
            particle.x += (particle.vx + self._parallax_x * 8.0 * particle.z) * dt * drift
            particle.y += (particle.vy + self._parallax_y * 6.0 * particle.z) * dt * drift
            particle.phase = (particle.phase + dt * (0.18 + particle.z * 0.28)) % 1.0
            if particle.x < -30:
                particle.x = w + 30
            elif particle.x > w + 30:
                particle.x = -30
            if particle.y < -30:
                particle.y = h + 30
            elif particle.y > h + 30:
                particle.y = -30

        for ripple in self._ripples:
            ripple.age += dt
        self._ripples = [r for r in self._ripples if r.age < 1.6]

        activity = 1.0 + self._audio_level * 1.4
        for packet in self._packets:
            packet.t = (packet.t + packet.speed * dt * activity) % 1.0

        self.update()

    def paintGL(self) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()

        self._draw_deep_background(painter, w, h)
        self._draw_parallax_grid(painter, w, h)
        self._draw_particle_field(painter, w, h)
        self._draw_network_routes(painter, w, h)
        self._draw_ripples(painter)
        self._draw_vignette(painter, w, h)
        painter.end()

    def _draw_deep_background(self, painter: QPainter, w: int, h: int) -> None:
        grad = QLinearGradient(0, 0, w * (0.75 + self._parallax_x * 0.08), h)
        grad.setColorAt(0.0, QColor(1, 4, 14))
        grad.setColorAt(0.45, BG_DEEP)
        grad.setColorAt(1.0, BG_MID)
        painter.fillRect(0, 0, w, h, grad)

        glow = QRadialGradient(
            QPointF(w * (0.5 + self._parallax_x * 0.025), h * (0.43 + self._parallax_y * 0.02)),
            max(w, h) * 0.62,
        )
        glow.setColorAt(0.0, QColor(0, 170, 255, int(34 + self._audio_level * 45)))
        glow.setColorAt(0.36, QColor(35, 60, 190, 34))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(0, 0, w, h, glow)

    def _draw_parallax_grid(self, painter: QPainter, w: int, h: int) -> None:
        horizon = h * 0.60 + self._parallax_y * 18.0
        offset = (self._time * 22.0) % 48.0

        painter.setPen(QPen(QColor(0, 170, 255, 28), 1))
        for i in range(22):
            t = i / 21.0
            x = w * (t - 0.5) * 1.6 + w * 0.5 + self._parallax_x * 35.0
            painter.drawLine(QPointF(w * 0.5, horizon), QPointF(x, h + 30))

        for i in range(18):
            y = horizon + ((i * 42.0 + offset) ** 1.05)
            if y > h:
                break
            alpha = int(clamp(62 - i * 3, 10, 64))
            painter.setPen(QPen(QColor(0, 176, 255, alpha), 1))
            painter.drawLine(QPointF(0, y), QPointF(w, y + self._parallax_y * 4.0))

        sweep_x = (self._time * 80.0) % (w + 220) - 110
        sweep = QLinearGradient(sweep_x - 100, 0, sweep_x + 100, 0)
        sweep.setColorAt(0.0, QColor(0, 210, 255, 0))
        sweep.setColorAt(0.5, QColor(0, 210, 255, int(14 + self._audio_level * 26)))
        sweep.setColorAt(1.0, QColor(0, 210, 255, 0))
        painter.fillRect(int(sweep_x - 100), 0, 200, h, sweep)

    def _draw_particle_field(self, painter: QPainter, w: int, h: int) -> None:
        painter.setCompositionMode(QPainter.CompositionMode_Plus)

        for idx, particle in enumerate(self._particles):
            x = particle.x + self._parallax_x * particle.z * 24.0
            y = particle.y + self._parallax_y * particle.z * 18.0
            twinkle = 0.38 + 0.62 * pulse(particle.phase)
            alpha = int((30 + particle.z * 115) * twinkle)
            size = particle.size * (0.6 + particle.z * 1.4) * (1.0 + self._audio_level * 0.45)
            color = QColor(88, 218, 255, alpha)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(x, y), size, size)

            if idx % 13 == 0:
                halo = QColor(0, 210, 255, alpha // 5)
                painter.setBrush(halo)
                painter.drawEllipse(QPointF(x, y), size * 4.4, size * 4.4)

        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        painter.setPen(QPen(QColor(0, 190, 255, 22), 1))
        samples = self._particles[::9]
        for i, a in enumerate(samples):
            for b in samples[i + 1 : i + 3]:
                dx = a.x - b.x
                dy = a.y - b.y
                if dx * dx + dy * dy < 21000:
                    painter.drawLine(QPointF(a.x, a.y), QPointF(b.x, b.y))

    def _build_routes(self) -> None:
        if not self._rects or "core" not in self._rects:
            return
        core = self._rects["core"]
        center = QPointF(core.center())
        routes: list[tuple[QPointF, QPointF, QPointF]] = []

        def add_route(rect_name: str, sx: float, sy: float, bend: float) -> None:
            rect = self._rects.get(rect_name)
            if rect is None:
                return
            start = QPointF(rect.left() + rect.width() * sx, rect.top() + rect.height() * sy)
            control = QPointF((start.x() + center.x()) * 0.5, (start.y() + center.y()) * 0.5 + bend)
            routes.append((start, control, center))

        add_route("left", 1.0, 0.22, -50)
        add_route("left", 1.0, 0.52, 8)
        add_route("left", 1.0, 0.82, 58)
        add_route("right", 0.0, 0.20, -55)
        add_route("right", 0.0, 0.50, 0)
        add_route("right", 0.0, 0.80, 55)
        add_route("console", 0.22, 0.0, -65)
        add_route("console", 0.78, 0.0, -65)
        add_route("top", 0.35, 1.0, 34)
        add_route("top", 0.65, 1.0, 34)
        self._routes = routes

    def _route_point(self, route: tuple[QPointF, QPointF, QPointF], t: float) -> QPointF:
        a, b, c = route
        inv = 1.0 - t
        return QPointF(
            inv * inv * a.x() + 2 * inv * t * b.x() + t * t * c.x(),
            inv * inv * a.y() + 2 * inv * t * b.y() + t * t * c.y(),
        )

    def _draw_network_routes(self, painter: QPainter, w: int, h: int) -> None:
        if not self._routes:
            center = QPointF(w * 0.5, h * 0.47)
            self._routes = [
                (QPointF(w * 0.13, h * 0.28), QPointF(w * 0.34, h * 0.20), center),
                (QPointF(w * 0.87, h * 0.28), QPointF(w * 0.66, h * 0.20), center),
                (QPointF(w * 0.20, h * 0.78), QPointF(w * 0.37, h * 0.62), center),
                (QPointF(w * 0.80, h * 0.78), QPointF(w * 0.63, h * 0.62), center),
            ]

        painter.setRenderHint(QPainter.Antialiasing)
        for i, route in enumerate(self._routes):
            start, control, end = route
            path = QPainterPath(start)
            path.quadTo(control, end)
            alpha = 34 + int(self._audio_level * 30)
            painter.setPen(QPen(QColor(0, 180, 255, alpha), 1.0))
            painter.drawPath(path)

            painter.setPen(QPen(QColor(90, 236, 255, 12), 5.0))
            painter.drawPath(path)

            node_color = [CYAN, VIOLET, GREEN, MAGENTA][i % 4]
            for step in (0.0, 1.0):
                point = self._route_point(route, step)
                painter.setPen(Qt.NoPen)
                painter.setBrush(with_alpha(node_color, 78))
                painter.drawEllipse(point, 3.0, 3.0)

        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for packet in self._packets:
            if not self._routes:
                break
            route = self._routes[packet.route % len(self._routes)]
            t = ease_out_cubic(packet.t)
            point = self._route_point(route, t)
            color = [CYAN, VIOLET, GREEN, MAGENTA][packet.hue % 4]
            alpha = int(125 + 95 * self._audio_level)
            painter.setPen(Qt.NoPen)
            painter.setBrush(with_alpha(color, alpha))
            painter.drawEllipse(point, 3.0 + self._audio_level * 2.2, 3.0 + self._audio_level * 2.2)
            painter.setBrush(with_alpha(color, 32))
            painter.drawEllipse(point, 14.0, 14.0)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

    def _draw_ripples(self, painter: QPainter) -> None:
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for ripple in self._ripples:
            t = ripple.age / 1.6
            radius = 24 + ease_out_cubic(t) * 420 * ripple.strength
            alpha = int((1.0 - t) * 90 * ripple.strength)
            painter.setPen(QPen(QColor(0, 220, 255, alpha), 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(ripple.x, ripple.y), radius, radius * 0.72)
            painter.setPen(QPen(QColor(150, 98, 255, alpha // 2), 1.0))
            painter.drawEllipse(QPointF(ripple.x, ripple.y), radius * 0.62, radius * 0.62)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

    def _draw_vignette(self, painter: QPainter, w: int, h: int) -> None:
        vignette = QRadialGradient(QPointF(w * 0.5, h * 0.45), max(w, h) * 0.72)
        vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
        vignette.setColorAt(0.72, QColor(0, 0, 0, 28))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 185))
        painter.fillRect(QRectF(0, 0, w, h), vignette)

        painter.setPen(QPen(LINE_DIM, 1))
        phase = (self._time * 0.22) % 1.0
        for y in range(0, h, 5):
            a = int(6 + 8 * pulse(phase + y * 0.003))
            painter.setPen(QPen(QColor(0, 120, 160, a), 1))
            painter.drawLine(0, y, w, y)
