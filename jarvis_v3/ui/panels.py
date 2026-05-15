"""Floating holographic panels for the fullscreen HUD."""

from __future__ import annotations

import math
import random
import time
from collections import deque
from datetime import datetime
from typing import Deque, List

import psutil
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
    QRadialGradient,
)

from ui.holo_renderer import Renderer


class FloatingPanel:
    def __init__(self, x: float, y: float, width: float, height: float, title: str) -> None:
        self.x = float(x)
        self.y = float(y)
        self.w = float(width)
        self.h = float(height)
        self.title = title
        self.renderer = Renderer()
        self._hover = 0.0
        self._tilt_x = 0.0
        self._tilt_y = 0.0
        self._float_offset = 0.0

    @property
    def rect(self) -> QRectF:
        return QRectF(self.x, self.y + self._float_offset, self.w, self.h)

    def contains(self, x: float, y: float) -> bool:
        return self.rect.contains(QPointF(x, y))

    def hit_header(self, x: float, y: float) -> bool:
        rect = self.rect
        return rect.left() <= x <= rect.right() and rect.top() <= y <= rect.top() + 34

    def move_by(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def set_position(self, x: float, y: float) -> None:
        self.x = float(x)
        self.y = float(y)

    def update(self, dt: float, anim) -> None:
        target_float = math.sin(anim.time * 0.6 + self.x * 0.01) * 5.0
        self._float_offset += (target_float - self._float_offset) * min(1.0, 3.0 * dt)

        cam_x, cam_y = anim.camera_offset
        self._tilt_x += (cam_x * 0.008 - self._tilt_x) * min(1.0, 4.0 * dt)
        self._tilt_y += (cam_y * 0.005 - self._tilt_y) * min(1.0, 4.0 * dt)
        self._hover = max(0.0, self._hover - dt * 1.2)

    def on_hover(self) -> None:
        self._hover = min(1.0, self._hover + 0.3)

    def _draw_base(self, painter: QPainter, anim) -> None:
        rect = self.rect
        energy = anim.energy * (0.85 + self._hover * 0.35)
        glow_alpha = int(40 + self._hover * 80)
        self.renderer.draw_panel_bg(
            painter,
            rect,
            self._tilt_x,
            self._tilt_y,
            glow_alpha=glow_alpha,
            energy=energy,
        )
        self.renderer.draw_panel_corners(painter, rect, size=14, energy=energy)
        self.renderer.draw_panel_header(painter, rect, self.title, energy=energy)
        scan_local = (anim.time * 80 + hash(self.title)) % self.h
        self.renderer.draw_panel_scan(painter, rect, scan_local, energy * 0.6)


class MetricsPanel(FloatingPanel):
    HISTORY = 60

    def __init__(self, x: float, y: float, width: float = 250, height: float = 320) -> None:
        super().__init__(x, y, width, height, "SYSTEM METRICS")
        self._cpu_hist: Deque[float] = deque([0.0] * self.HISTORY, self.HISTORY)
        self._ram = 0.0
        self._cpu = 0.0
        self._gpu = 0.0
        self._net = 0.0
        self._disk = 0.0
        self._temp = 42.0
        self._t_sample = 0.0
        self._gpu_target = random.uniform(15, 65)
        self._font_sm = QFont("Courier New", 8)
        self._font_sm.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)

    def update(self, dt: float, anim) -> None:
        super().update(dt, anim)
        self._t_sample += dt
        if self._t_sample < 0.5:
            return

        self._t_sample = 0.0
        try:
            self._cpu = psutil.cpu_percent(interval=None)
            self._ram = psutil.virtual_memory().percent
            io = psutil.net_io_counters()
            self._net = min((io.bytes_sent + io.bytes_recv) / 1e7, 100)
            self._disk = psutil.disk_usage("/").percent
        except Exception:
            pass

        self._temp = max(35, min(95, self._temp + random.uniform(-1, 1.5)))
        self._gpu_target = max(5, min(95, self._gpu_target + random.uniform(-3, 3)))
        self._gpu += (self._gpu_target - self._gpu) * 0.15
        self._cpu_hist.append(self._cpu)

    def draw(self, painter: QPainter, anim) -> None:
        self._draw_base(painter, anim)
        rect = self.rect
        bx = rect.x() + 12
        by = rect.y() + 40
        energy = anim.energy

        bars = [
            ("CPU", self._cpu / 100, f"{self._cpu:.0f}%", QColor(0, 180, 255)),
            ("RAM", self._ram / 100, f"{self._ram:.0f}%", QColor(0, 255, 140)),
            ("GPU", self._gpu / 100, f"{self._gpu:.0f}%", QColor(255, 170, 20)),
            ("DISK", self._disk / 100, f"{self._disk:.0f}%", QColor(190, 100, 255)),
            ("NET", self._net / 100, f"{self._net:.1f}%", QColor(0, 255, 255)),
        ]
        for i, (label, value, value_text, color) in enumerate(bars):
            self.renderer.draw_metric_bar(
                painter,
                bx,
                by + i * 38,
                rect.width() - 24,
                30,
                value,
                label,
                value_text,
                color,
                anim.time,
            )

        self._draw_sparkline(painter, QRectF(bx, by + 5 * 38 + 8, rect.width() - 24, 46), energy)

        temp_y = by + 5 * 38 + 60
        painter.setFont(self._font_sm)
        temp_color = QColor(255, 90, 30) if self._temp > 80 else QColor(0, 255, 255)
        painter.setPen(QColor(0, 180, 200, 140))
        painter.drawText(QPointF(bx, temp_y), "TEMP")
        painter.setPen(temp_color)
        painter.drawText(QPointF(bx + 42, temp_y), f"{self._temp:.1f} C")

    def _draw_sparkline(self, painter: QPainter, rect: QRectF, energy: float) -> None:
        data = list(self._cpu_hist)
        if len(data) < 2:
            return
        painter.save()
        painter.setClipRect(rect)
        path = QPainterPath()
        step = rect.width() / (len(data) - 1)
        for i, value in enumerate(data):
            px = rect.x() + i * step
            py = rect.bottom() - (value / 100) * rect.height()
            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)

        fill = QPainterPath(path)
        fill.lineTo(rect.right(), rect.bottom())
        fill.lineTo(rect.x(), rect.bottom())
        fill.closeSubpath()
        grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
        grad.setColorAt(0, QColor(0, 200, 255, int(80 * energy)))
        grad.setColorAt(1, QColor(0, 50, 100, 0))
        painter.fillPath(fill, QBrush(grad))
        painter.setPen(QPen(QColor(0, 255, 255, int(180 * energy)), 1.2))
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        painter.drawPath(path)
        painter.restore()


class AIStatusPanel(FloatingPanel):
    def __init__(self, x: float, y: float, width: float = 230, height: float = 310) -> None:
        super().__init__(x, y, width, height, "AI CORE STATUS")
        self._state = "ONLINE"
        self._voice_active = False
        self._wave_data: List[float] = [0.0] * 64
        self._wave_phase = 0.0
        self._uptime_start = time.time()
        self._font_state = QFont("Courier New", 13, QFont.Bold)
        self._font_state.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        self._font_sm = QFont("Courier New", 8)
        self._font_sm.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
        self._neural_load = 0.0
        self._neural_target = 0.65

    def set_state(self, state: str) -> None:
        self._state = state.upper()

    def set_voice(self, active: bool) -> None:
        self._voice_active = active

    def update(self, dt: float, anim) -> None:
        super().update(dt, anim)
        self._wave_phase += dt * (4.0 if self._voice_active else 1.2)
        self._neural_target = max(0.1, min(0.99, self._neural_target + random.uniform(-0.02, 0.02)))
        self._neural_load += (self._neural_target - self._neural_load) * 2.0 * dt
        amp = 0.7 if self._voice_active else 0.15
        for i in range(len(self._wave_data)):
            base = math.sin(i * 0.3 + self._wave_phase) * amp
            noise = random.uniform(-0.05, 0.05) if self._voice_active else 0
            self._wave_data[i] = base + noise

    def draw(self, painter: QPainter, anim) -> None:
        self._draw_base(painter, anim)
        rect = self.rect
        energy = anim.energy
        bx = rect.x() + 14
        by = rect.y() + 42
        t = anim.time

        self._draw_energy_ring(painter, rect.x() + rect.width() / 2, by + 38, 30, energy, t)

        pulse_alpha = int((math.sin(t * 2) * 0.3 + 0.7) * 220 * energy)
        painter.setFont(self._font_state)
        painter.setPen(QColor(0, 255, 255, pulse_alpha))
        state = self._state[:11]
        width = QFontMetrics(self._font_state).horizontalAdvance(state)
        painter.drawText(QPointF(rect.x() + (rect.width() - width) / 2, by + 88), state)

        uptime = int(time.time() - self._uptime_start)
        hours, minutes, seconds = uptime // 3600, (uptime % 3600) // 60, uptime % 60
        voice_str = "ACTIVE" if self._voice_active else "IDLE"
        rows = [
            ("CORTEX", "ONLINE", QColor(0, 255, 120)),
            ("VOICE", voice_str, QColor(0, 255, 120) if self._voice_active else QColor(0, 180, 200)),
            ("SECURITY", "ENGAGED", QColor(0, 255, 120)),
            ("UPTIME", f"{hours:02d}:{minutes:02d}:{seconds:02d}", QColor(0, 200, 255)),
            ("NEURAL", f"{self._neural_load * 100:.0f}%", QColor(200, 100, 255)),
        ]

        painter.setFont(self._font_sm)
        row_y = by + 100
        for label, value, value_color in rows:
            dot_x = bx + 4
            dot_y = row_y - 4
            dot_color = QColor(value_color)
            dot_color.setAlpha(int(abs(math.sin(t * 2 + row_y)) * 120 + 80))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(dot_color))
            painter.drawEllipse(QPointF(dot_x, dot_y), 3, 3)

            painter.setBrush(Qt.NoBrush)
            painter.setPen(QColor(0, 160, 180, int(160 * energy)))
            painter.drawText(QPointF(bx + 14, row_y), label)
            painter.setPen(value_color)
            value_width = QFontMetrics(self._font_sm).horizontalAdvance(value)
            painter.drawText(QPointF(rect.x() + rect.width() - value_width - 14, row_y), value)
            painter.setPen(QPen(QColor(0, 255, 255, 15), 0.5))
            painter.drawLine(QPointF(bx, row_y + 4), QPointF(rect.x() + rect.width() - 14, row_y + 4))
            row_y += 22

        wf_rect = QRectF(bx, row_y + 8, rect.width() - 28, 36)
        wf_color = QColor(0, 255, 120) if self._voice_active else QColor(0, 200, 255)
        self.renderer.draw_waveform(
            painter,
            wf_rect.x(),
            wf_rect.y(),
            wf_rect.width(),
            wf_rect.height(),
            self._wave_data,
            wf_color,
            energy,
        )

    def _draw_energy_ring(self, painter: QPainter, cx: float, cy: float, radius: float, energy: float, t: float) -> None:
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for i in range(4):
            ring_radius = radius - i * 6
            if ring_radius <= 0:
                continue
            alpha = int((0.2 + i * 0.15) * 220 * energy)
            painter.setPen(QPen(QColor(0, 255, 255, alpha), 1.2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), ring_radius, ring_radius * 0.45)
        glow = QRadialGradient(cx, cy, 8 + math.sin(t * 8) * 1.5)
        glow.setColorAt(0, QColor(220, 255, 255, int(240 * energy)))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(cx - 10, cy - 10, 20, 20), QBrush(glow))
        painter.restore()


class TopHUDBar:
    def __init__(self, width: int, height: int) -> None:
        self.w = width
        self.h = height
        self._font_logo = QFont("Courier New", 16, QFont.Bold)
        self._font_logo.setLetterSpacing(QFont.AbsoluteSpacing, 8)
        self._font_sm = QFont("Courier New", 9)
        self._font_sm.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        self._font_clock = QFont("Courier New", 11, QFont.Bold)
        self._font_clock.setLetterSpacing(QFont.AbsoluteSpacing, 3)

    def resize(self, width: int, height: int) -> None:
        self.w = width
        self.h = height

    def draw(self, painter: QPainter, anim) -> None:
        t = anim.time
        energy = anim.energy
        bar_h = 44
        grad = QLinearGradient(0, 0, 0, bar_h)
        grad.setColorAt(0, QColor(0, 15, 30, 210))
        grad.setColorAt(1, QColor(0, 5, 15, 160))
        painter.fillRect(QRectF(0, 0, self.w, bar_h), QBrush(grad))

        painter.setPen(QPen(QColor(0, 255, 255, int(60 * energy)), 1))
        painter.drawLine(QPointF(0, bar_h), QPointF(self.w, bar_h))
        painter.setPen(QPen(QColor(0, 255, 255, int(15 * energy)), 3))
        painter.drawLine(QPointF(0, bar_h + 1), QPointF(self.w, bar_h + 1))

        painter.setFont(self._font_logo)
        pulse_alpha = int((math.sin(t * 1.2) * 0.15 + 0.85) * 240 * energy)
        painter.setPen(QColor(0, 255, 255, pulse_alpha))
        painter.drawText(QPointF(20, 28), "JARVIS")

        painter.setFont(self._font_sm)
        painter.setPen(QColor(0, 160, 180, int(120 * energy)))
        painter.drawText(QPointF(128, 20), "ARTIFICIAL INTELLIGENCE INTERFACE")

        painter.setPen(QPen(QColor(0, 255, 255, 40), 1))
        for dx in [122, 382, 642]:
            painter.drawLine(QPointF(dx, 8), QPointF(dx, bar_h - 8))

        statuses = [
            (397, "CORE ONLINE", QColor(0, 255, 120)),
            (508, "NET ACTIVE", QColor(0, 200, 255)),
            (610, "SEC ENGAGED", QColor(255, 200, 0)),
        ]
        painter.setFont(self._font_sm)
        for sx, label, color in statuses:
            blink = abs(math.sin(t * 1.5 + sx)) > 0.4
            dot = QColor(color)
            dot.setAlpha(220 if blink else 100)
            painter.setPen(dot)
            painter.drawText(QPointF(sx, 22), "o")
            painter.setPen(QColor(color.red(), color.green(), color.blue(), int(140 * energy)))
            painter.drawText(QPointF(sx + 14, 22), label)

        now = datetime.now()
        painter.setFont(self._font_clock)
        painter.setPen(QColor(0, 220, 240, int(220 * energy)))
        painter.drawText(QPointF(self.w - 160, 26), now.strftime("%H:%M:%S"))
        painter.setFont(self._font_sm)
        painter.setPen(QColor(0, 150, 170, int(130 * energy)))
        painter.drawText(QPointF(self.w - 160, 38), now.strftime("%Y.%m.%d"))

        sx = (t * 200) % (self.w + 100) - 50
        shimmer = QLinearGradient(sx, 0, sx + 60, 0)
        shimmer.setColorAt(0, QColor(0, 0, 0, 0))
        shimmer.setColorAt(0.5, QColor(0, 255, 255, int(20 * energy)))
        shimmer.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(sx, 0, 60, bar_h), QBrush(shimmer))


class CornerHUD:
    def __init__(self, width: int, height: int) -> None:
        self.w = width
        self.h = height
        self._font = QFont("Courier New", 8)
        self._font.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)

    def resize(self, width: int, height: int) -> None:
        self.w = width
        self.h = height

    def draw(self, painter: QPainter, anim) -> None:
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
        except Exception:
            cpu = mem = disk = 0.0
        t = anim.time
        energy = anim.energy
        corner_size = 60
        corners = [
            (0, 44, 1, 1, "CPU", f"{cpu:.0f}%"),
            (self.w, 44, -1, 1, "MEM", f"{mem:.0f}%"),
            (0, self.h, 1, -1, "DSK", f"{disk:.0f}%"),
            (self.w, self.h, -1, -1, "SYS", "OK"),
        ]
        painter.setFont(self._font)
        painter.setPen(QPen(QColor(0, 255, 255, int(60 * energy)), 1.0))
        for cx, cy, mx, my, label, value in corners:
            painter.drawLine(QPointF(cx, cy), QPointF(cx + mx * corner_size, cy))
            painter.drawLine(QPointF(cx, cy), QPointF(cx, cy + my * corner_size))
            blink_alpha = int(abs(math.sin(t * 2 + cx)) * 180 + 60)
            text_x = cx + mx * 8 + (0 if mx > 0 else -34)
            painter.setPen(QColor(0, 255, 255, int(blink_alpha * energy)))
            painter.drawText(QPointF(text_x, cy + my * 18), label)
            painter.setPen(QColor(0, 220, 240, int(160 * energy)))
            painter.drawText(QPointF(text_x, cy + my * 30), value)
            painter.setPen(QPen(QColor(0, 255, 255, int(60 * energy)), 1.0))
