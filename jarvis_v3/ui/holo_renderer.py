"""QPainter helpers for the holographic HUD skin."""

from __future__ import annotations

import math
from typing import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
    QPolygonF,
    QRadialGradient,
)


CYAN = QColor(0, 255, 255)
BLUE = QColor(0, 160, 255)
GREEN = QColor(0, 255, 140)
WHITE_CORE = QColor(230, 255, 255)


def _alpha(color: QColor, value: int | float) -> QColor:
    out = QColor(color)
    if isinstance(value, float):
        out.setAlphaF(max(0.0, min(1.0, value)))
    else:
        out.setAlpha(max(0, min(255, value)))
    return out


class Renderer:
    """Small, dependency-free renderer used by the holographic HUD modules."""

    def __init__(self) -> None:
        self.font_tiny = QFont("Courier New", 8)
        self.font_tiny.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
        self.font_label = QFont("Courier New", 9, QFont.Bold)
        self.font_label.setLetterSpacing(QFont.AbsoluteSpacing, 1.6)
        self.font_title = QFont("Courier New", 10, QFont.Bold)
        self.font_title.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)

    def _panel_path(self, rect: QRectF, bevel: float = 12.0) -> QPainterPath:
        b = min(bevel, rect.width() * 0.22, rect.height() * 0.22)
        path = QPainterPath()
        path.moveTo(rect.left() + b, rect.top())
        path.lineTo(rect.right() - b, rect.top())
        path.lineTo(rect.right(), rect.top() + b)
        path.lineTo(rect.right(), rect.bottom() - b)
        path.lineTo(rect.right() - b, rect.bottom())
        path.lineTo(rect.left() + b, rect.bottom())
        path.lineTo(rect.left(), rect.bottom() - b)
        path.lineTo(rect.left(), rect.top() + b)
        path.closeSubpath()
        return path

    def draw_panel_bg(
        self,
        painter: QPainter,
        rect: QRectF,
        tilt_x: float = 0.0,
        tilt_y: float = 0.0,
        glow_alpha: int = 40,
        energy: float = 1.0,
    ) -> None:
        painter.save()
        path = self._panel_path(rect)

        fill = QLinearGradient(rect.topLeft(), rect.bottomRight())
        fill.setColorAt(0.0, QColor(0, 34, 58, 190))
        fill.setColorAt(0.55, QColor(1, 14, 34, 210))
        fill.setColorAt(1.0, QColor(0, 7, 18, 232))
        painter.fillPath(path, QBrush(fill))

        painter.setPen(QPen(QColor(0, 255, 255, int(70 * energy)), 1.0))
        painter.drawPath(path)

        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        glow = QPen(QColor(0, 210, 255, max(12, glow_alpha)), 5.0)
        glow.setJoinStyle(Qt.RoundJoin)
        painter.setPen(glow)
        painter.drawPath(path)

        shear = QPen(QColor(0, 255, 255, int(18 * energy)), 1.0)
        painter.setPen(shear)
        painter.drawLine(
            QPointF(rect.left() + 14 + tilt_x, rect.top() + 34 + tilt_y),
            QPointF(rect.right() - 14 + tilt_x * 0.35, rect.top() + 34 - tilt_y),
        )
        painter.restore()

    def draw_panel_corners(
        self, painter: QPainter, rect: QRectF, size: float = 14.0, energy: float = 1.0
    ) -> None:
        painter.save()
        painter.setPen(QPen(QColor(0, 255, 255, int(150 * energy)), 1.4))
        arms = [
            (rect.left(), rect.top(), 1, 1),
            (rect.right(), rect.top(), -1, 1),
            (rect.left(), rect.bottom(), 1, -1),
            (rect.right(), rect.bottom(), -1, -1),
        ]
        for x, y, sx, sy in arms:
            painter.drawLine(QPointF(x, y), QPointF(x + sx * size, y))
            painter.drawLine(QPointF(x, y), QPointF(x, y + sy * size))
        painter.restore()

    def draw_panel_header(
        self, painter: QPainter, rect: QRectF, title: str, energy: float = 1.0
    ) -> None:
        painter.save()
        header = QRectF(rect.left(), rect.top(), rect.width(), 34)
        grad = QLinearGradient(header.topLeft(), header.bottomLeft())
        grad.setColorAt(0.0, QColor(0, 80, 120, 90))
        grad.setColorAt(1.0, QColor(0, 20, 34, 0))
        painter.fillRect(header, QBrush(grad))

        painter.setFont(self.font_title)
        painter.setPen(QColor(222, 255, 255, int(220 * energy)))
        painter.drawText(QPointF(rect.left() + 14, rect.top() + 22), title)

        painter.setPen(QPen(QColor(0, 255, 255, int(58 * energy)), 1))
        painter.drawLine(QPointF(rect.left() + 10, rect.top() + 32), QPointF(rect.right() - 10, rect.top() + 32))
        painter.restore()

    def draw_panel_scan(
        self, painter: QPainter, rect: QRectF, y: float, energy: float = 1.0
    ) -> None:
        painter.save()
        y = rect.top() + y
        scan = QLinearGradient(rect.left(), y - 9, rect.left(), y + 9)
        scan.setColorAt(0.0, QColor(0, 255, 255, 0))
        scan.setColorAt(0.5, QColor(0, 255, 255, int(20 * energy)))
        scan.setColorAt(1.0, QColor(0, 255, 255, 0))
        painter.fillRect(QRectF(rect.left(), y - 9, rect.width(), 18), QBrush(scan))
        painter.restore()

    def draw_metric_bar(
        self,
        painter: QPainter,
        x: float,
        y: float,
        width: float,
        height: float,
        value: float,
        label: str,
        value_text: str,
        color: QColor,
        t: float,
    ) -> None:
        value = max(0.0, min(1.0, value))
        painter.save()
        painter.setFont(self.font_tiny)
        painter.setPen(QColor(135, 220, 240, 185))
        painter.drawText(QPointF(x, y + 10), label)
        painter.setPen(_alpha(color, 220))
        painter.drawText(QPointF(x + width - QFontMetrics(self.font_tiny).horizontalAdvance(value_text), y + 10), value_text)

        bar = QRectF(x, y + 15, width, max(5, height - 18))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 255, 255, 18))
        painter.drawRect(bar)

        fill = QRectF(bar.left(), bar.top(), bar.width() * value, bar.height())
        grad = QLinearGradient(fill.topLeft(), fill.topRight())
        grad.setColorAt(0.0, _alpha(color, 80))
        grad.setColorAt(0.55, _alpha(color, 215))
        grad.setColorAt(1.0, _alpha(WHITE_CORE, 230))
        painter.fillRect(fill, QBrush(grad))

        shimmer_x = fill.left() + (t * 54.0 % max(fill.width() + 30.0, 30.0)) - 30.0
        shimmer = QLinearGradient(shimmer_x, fill.top(), shimmer_x + 30, fill.top())
        shimmer.setColorAt(0.0, QColor(255, 255, 255, 0))
        shimmer.setColorAt(0.5, QColor(255, 255, 255, 55))
        shimmer.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(shimmer_x, fill.top(), 30, fill.height()), QBrush(shimmer))
        painter.restore()

    def draw_waveform(
        self,
        painter: QPainter,
        x: float,
        y: float,
        width: float,
        height: float,
        samples: Sequence[float],
        color: QColor,
        energy: float = 1.0,
    ) -> None:
        if not samples:
            return
        painter.save()
        path = QPainterPath()
        mid = y + height / 2
        step = width / max(1, len(samples) - 1)
        path.moveTo(x, mid)
        for i, sample in enumerate(samples):
            path.lineTo(x + i * step, mid - sample * height * 0.45)
        pen = QPen(QColor(color.red(), color.green(), color.blue(), int(190 * energy)), 1.3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.restore()

    def draw_starfield_particle(self, painter: QPainter, x: float, y: float, size: float, alpha: float) -> None:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(110, 235, 255, int(max(0.0, min(1.0, alpha)) * 170)))
        painter.drawEllipse(QPointF(x, y), max(0.6, size), max(0.6, size))

    def draw_grid(
        self, painter: QPainter, width: int, height: int, ox: float, oy: float, spacing: int = 65
    ) -> None:
        painter.save()
        horizon = height * 0.60 + oy
        painter.setPen(QPen(QColor(0, 190, 255, 26), 1))
        for i in range(-18, 19):
            x = width / 2 + i * spacing + ox
            painter.drawLine(QPointF(width / 2 + ox * 0.2, horizon), QPointF(x, height + 20))
        offset = (oy * 0.6) % spacing
        for i in range(18):
            y = horizon + i * spacing * (1.0 + i * 0.04) + offset
            if y > height:
                break
            painter.drawLine(QPointF(0, y), QPointF(width, y))
        painter.restore()

    def draw_horizon(
        self, painter: QPainter, width: int, height: int, y: float, alpha: float = 1.0
    ) -> None:
        painter.save()
        painter.setPen(QPen(QColor(0, 255, 255, int(60 * alpha)), 1.0))
        painter.drawLine(QPointF(0, y), QPointF(width, y))
        glow = QLinearGradient(0, y - 80, 0, y + 120)
        glow.setColorAt(0.0, QColor(0, 255, 255, 0))
        glow.setColorAt(0.5, QColor(0, 170, 255, int(18 * alpha)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(0, y - 80, width, 200), QBrush(glow))
        painter.restore()

    def draw_core_glow(self, painter: QPainter, cx: float, cy: float, energy: float, t: float) -> None:
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        r = 260 + math.sin(t * 1.2) * 18
        glow = QRadialGradient(cx, cy, r)
        glow.setColorAt(0.0, QColor(0, 255, 255, int(44 * energy)))
        glow.setColorAt(0.26, QColor(0, 150, 255, int(36 * energy)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(cx - r, cy - r, r * 2, r * 2), QBrush(glow))
        painter.restore()

    def draw_ring(
        self,
        painter: QPainter,
        cx: float,
        cy: float,
        radius: float,
        angle: float,
        color: QColor,
        width: float = 1.0,
        dash: Sequence[float] | None = None,
        glow_width: float = 5.0,
        energy: float = 1.0,
    ) -> None:
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

        glow = QPen(_alpha(color, int(35 * energy)), width + glow_width)
        glow.setCapStyle(Qt.RoundCap)
        if dash:
            glow.setDashPattern(list(dash))
        painter.setPen(glow)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(rect, int(angle * 16), int(290 * 16))

        pen = QPen(color, width)
        pen.setCapStyle(Qt.RoundCap)
        if dash:
            pen.setDashPattern(list(dash))
        painter.setPen(pen)
        painter.drawArc(rect, int(angle * 16), int(290 * 16))
        painter.restore()

    def draw_ring_accents(
        self, painter: QPainter, cx: float, cy: float, radius: float, angle: float, count: int, energy: float
    ) -> None:
        painter.save()
        painter.setPen(QPen(QColor(220, 255, 255, int(130 * energy)), 1.5))
        for i in range(count):
            a = math.radians(angle + i * (360 / count))
            x1 = cx + math.cos(a) * (radius - 8)
            y1 = cy + math.sin(a) * (radius - 8)
            x2 = cx + math.cos(a) * (radius + 9)
            y2 = cy + math.sin(a) * (radius + 9)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        painter.restore()

    def draw_orbital_particle(
        self, painter: QPainter, x: float, y: float, size: float, trail: Sequence[tuple[float, float]], energy: float
    ) -> None:
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        if len(trail) > 1:
            for idx, (tx, ty) in enumerate(trail):
                alpha = int((idx + 1) / len(trail) * 80 * energy)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(0, 255, 255, alpha))
                painter.drawEllipse(QPointF(tx, ty), size * 0.45, size * 0.45)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(215, 255, 255, int(230 * energy)))
        painter.drawEllipse(QPointF(x, y), size, size)
        painter.setBrush(QColor(0, 255, 255, int(42 * energy)))
        painter.drawEllipse(QPointF(x, y), size * 4.0, size * 4.0)
        painter.restore()

    def draw_cross_lines(self, painter: QPainter, cx: float, cy: float, angle: float, radius: float, energy: float) -> None:
        painter.save()
        painter.setPen(QPen(QColor(0, 255, 255, int(42 * energy)), 1))
        for i in range(4):
            a = angle + i * math.pi / 2
            painter.drawLine(
                QPointF(cx + math.cos(a) * 22, cy + math.sin(a) * 22),
                QPointF(cx + math.cos(a) * radius, cy + math.sin(a) * radius),
            )
        painter.restore()

    def draw_pulse_rings(
        self, painter: QPainter, cx: float, cy: float, t: float, energy: float, count: int = 4
    ) -> None:
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for i in range(count):
            phase = (t * 0.55 + i / count) % 1.0
            r = 26 + phase * 86
            alpha = int((1.0 - phase) * 90 * energy)
            painter.setPen(QPen(QColor(0, 255, 255, alpha), 1.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), r, r)
        painter.restore()

    def draw_hex_core(self, painter: QPainter, cx: float, cy: float, radius: float, angle: float, energy: float) -> None:
        points = QPolygonF()
        for i in range(6):
            a = angle + i * math.tau / 6
            points.append(QPointF(cx + math.cos(a) * radius, cy + math.sin(a) * radius))
        painter.save()
        painter.setPen(QPen(QColor(0, 255, 255, int(190 * energy)), 1.4))
        painter.setBrush(QColor(0, 255, 255, int(22 * energy)))
        painter.drawPolygon(points)
        painter.restore()

    def draw_inner_core(self, painter: QPainter, cx: float, cy: float, radius: float, energy: float, t: float) -> None:
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        grad = QRadialGradient(cx, cy, radius * (1.25 + 0.08 * math.sin(t * 5)))
        grad.setColorAt(0.0, QColor(255, 255, 255, int(235 * energy)))
        grad.setColorAt(0.38, QColor(0, 255, 255, int(210 * energy)))
        grad.setColorAt(1.0, QColor(0, 70, 120, 0))
        r = radius * 1.6
        painter.fillRect(QRectF(cx - r, cy - r, r * 2, r * 2), QBrush(grad))

        conic = QConicalGradient(QPointF(cx, cy), t * -90)
        conic.setColorAt(0.0, QColor(0, 255, 255, 0))
        conic.setColorAt(0.14, QColor(255, 255, 255, 170))
        conic.setColorAt(0.22, QColor(0, 255, 255, 0))
        conic.setColorAt(1.0, QColor(0, 255, 255, 0))
        painter.setBrush(conic)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), radius * 1.85, radius * 1.85)
        painter.restore()

    def draw_scan_lines(self, painter: QPainter, width: int, height: int, sy: float, strength: float) -> None:
        painter.save()
        painter.setPen(Qt.NoPen)
        grad = QLinearGradient(0, sy - 24, 0, sy + 24)
        grad.setColorAt(0.0, QColor(0, 255, 255, 0))
        grad.setColorAt(0.5, QColor(0, 255, 255, int(18 * strength)))
        grad.setColorAt(1.0, QColor(0, 255, 255, 0))
        painter.fillRect(QRectF(0, sy - 24, width, 48), QBrush(grad))
        painter.setPen(QPen(QColor(0, 255, 255, 12), 1))
        for y in range(0, height, 4):
            painter.drawLine(QPointF(0, y), QPointF(width, y))
        painter.restore()

    def draw_vignette(self, painter: QPainter, width: int, height: int, strength: float) -> None:
        painter.save()
        r = max(width, height) * 0.72
        grad = QRadialGradient(width / 2, height / 2, r)
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad.setColorAt(0.74, QColor(0, 0, 0, int(80 * strength)))
        grad.setColorAt(1.0, QColor(0, 0, 0, int(230 * strength)))
        painter.fillRect(QRectF(0, 0, width, height), QBrush(grad))
        painter.restore()
