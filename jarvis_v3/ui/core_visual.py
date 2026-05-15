"""Animated holographic AI core for the fullscreen HUD."""

from __future__ import annotations

import math
import random
from typing import List, Tuple

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QBrush, QPainter, QRadialGradient

from ui.holo_renderer import Renderer


class OrbitalParticle:
    def __init__(self, index: int, total: int) -> None:
        self.index = index
        self.angle = (index / total) * math.tau + random.uniform(0, 0.5)
        self.radius = 80 + index * 18 + random.uniform(-5, 5)
        self.speed = (0.25 + index * 0.06) * (1 if index % 2 == 0 else -1)
        self.size = random.uniform(2.5, 5.0)
        self.trail: List[Tuple[float, float]] = []
        self.trail_max = 25
        self.ellipse_y = 0.36

    def update(self, dt: float, energy: float) -> None:
        self.angle += self.speed * dt * energy

    def get_pos(self, cx: float, cy: float, energy: float) -> tuple[float, float]:
        x = cx + math.cos(self.angle) * self.radius * energy
        y = cy + math.sin(self.angle) * self.radius * energy * self.ellipse_y
        return x, y

    def push_trail(self, x: float, y: float) -> None:
        self.trail.append((x, y))
        if len(self.trail) > self.trail_max:
            self.trail.pop(0)


class StarParticle:
    def __init__(self, width: int, height: int) -> None:
        self.w = width
        self.h = height
        self.reset(random_z=True)

    def reset(self, random_z: bool = False) -> None:
        self.x = random.uniform(-self.w * 0.6, self.w * 0.6)
        self.y = random.uniform(-self.h * 0.5, self.h * 0.5)
        self.z = random.uniform(200, 2000) if random_z else 2000
        self.vz = random.uniform(1.5, 4.0)
        self.size = random.uniform(0.4, 2.0)
        self.bright = random.uniform(0.3, 1.0)

    def update(self, dt: float) -> None:
        self.z -= self.vz * dt * 60
        if self.z < 1:
            self.reset()

    def get_screen(self, cx: float, cy: float) -> tuple[float, float, float, float]:
        if self.z < 1:
            return -1, -1, 0, 0
        scale = 800 / self.z
        return (
            cx + self.x * scale,
            cy + self.y * scale,
            self.size * scale,
            (1 - self.z / 2000) * self.bright,
        )


class CoreVisual:
    """Draws the center reactor, starfield, grid, and overlay scan layers."""

    RINGS = [
        (148, 1.2, 0.40, [10, 5], 160),
        (122, 0.8, -0.65, [5, 10], 140),
        (96, 1.8, 0.85, [], 200),
        (72, 0.8, -1.15, [3, 7], 120),
        (52, 1.4, 1.55, [], 220),
        (170, 0.6, -0.25, [15, 10], 80),
    ]

    def __init__(self, width: int, height: int) -> None:
        self.w = max(width, 1)
        self.h = max(height, 1)
        self.cx = self.w / 2
        self.cy = self.h / 2 - 20
        self.renderer = Renderer()
        self.orbitals = [OrbitalParticle(i, 8) for i in range(8)]
        self.stars = [StarParticle(self.w, self.h) for _ in range(140)]
        self._speaking = False
        self._speak_intensity = 0.0

    def resize(self, width: int, height: int) -> None:
        self.w = max(width, 1)
        self.h = max(height, 1)
        self.cx = self.w / 2
        self.cy = self.h / 2 - 20
        for star in self.stars:
            star.w = self.w
            star.h = self.h

    def set_speaking(self, speaking: bool, intensity: float = 1.0) -> None:
        self._speaking = speaking
        self._speak_intensity = max(0.0, min(1.0, intensity))

    def update(self, dt: float, anim) -> None:
        energy = anim.energy
        cam_x, cam_y = anim.camera_offset
        cx = self.cx + cam_x * 0.3
        cy = self.cy + cam_y * 0.3
        for orbital in self.orbitals:
            orbital.update(dt, energy)
            orbital.push_trail(*orbital.get_pos(cx, cy, energy))
        for star in self.stars:
            star.update(dt)

    def draw_starfield(self, painter: QPainter, anim) -> None:
        cx, cy = self._cam(anim, 0.08)
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        for star in self.stars:
            sx, sy, sz, sa = star.get_screen(cx, cy)
            if 0 <= sx <= self.w and 0 <= sy <= self.h:
                self.renderer.draw_starfield_particle(painter, sx, sy, sz, sa)
        painter.restore()

    def draw_grid(self, painter: QPainter, anim) -> None:
        cam_x, cam_y = anim.camera_offset
        self.renderer.draw_grid(painter, self.w, self.h, cam_x * 0.05, cam_y * 0.05, spacing=65)

    def draw_horizon(self, painter: QPainter, anim) -> None:
        _, cam_y = anim.camera_offset
        cy = self.cy + cam_y * 0.1 + 60
        self.renderer.draw_horizon(painter, self.w, self.h, cy, alpha=anim.breathe(0.3) * 0.7 + 0.3)

    def draw_core_glow(self, painter: QPainter, anim) -> None:
        cx, cy = self._cam(anim, 0.3)
        self.renderer.draw_core_glow(painter, cx, cy, anim.energy, anim.time)

    def draw_rings(self, painter: QPainter, anim) -> None:
        cx, cy = self._cam(anim, 0.3)
        energy = anim.energy
        palette = [
            QColor(0, 255, 255),
            QColor(0, 180, 255),
            QColor(50, 255, 200),
        ]
        for i, (base_r, width, _, dash, alpha) in enumerate(self.RINGS):
            angle = anim.ring_angles[i]
            radius = base_r * energy
            color = QColor(palette[i % 3])
            color.setAlpha(int(alpha * energy))
            self.renderer.draw_ring(
                painter,
                cx,
                cy,
                radius,
                angle,
                color,
                width=width,
                dash=[float(item) for item in dash] if dash else [],
                glow_width=6.0,
                energy=energy,
            )
            if i % 2 == 0:
                self.renderer.draw_ring_accents(painter, cx, cy, radius, angle, 4, energy * 0.9)

    def draw_orbitals(self, painter: QPainter, anim) -> None:
        cx, cy = self._cam(anim, 0.3)
        for orbital in self.orbitals:
            x, y = orbital.get_pos(cx, cy, anim.energy)
            self.renderer.draw_orbital_particle(painter, x, y, orbital.size, orbital.trail, anim.energy)

    def draw_inner_core(self, painter: QPainter, anim) -> None:
        cx, cy = self._cam(anim, 0.3)
        energy = anim.energy
        t = anim.time
        self.renderer.draw_cross_lines(painter, cx, cy, t * 0.3, 120, energy)
        self.renderer.draw_pulse_rings(painter, cx, cy, t, energy, count=4)
        self.renderer.draw_hex_core(painter, cx, cy, 24 * energy, t * 0.5, energy)
        self.renderer.draw_inner_core(painter, cx, cy, 36, energy, t)
        if self._speaking:
            burst = 50 + self._speak_intensity * 30 * abs(math.sin(t * 12))
            painter.save()
            painter.setCompositionMode(QPainter.CompositionMode_Plus)
            glow = QRadialGradient(cx, cy, burst)
            glow.setColorAt(0, QColor(0, 255, 120, int(80 * self._speak_intensity)))
            glow.setColorAt(1, QColor(0, 0, 0, 0))
            painter.fillRect(QRectF(cx - burst, cy - burst, burst * 2, burst * 2), QBrush(glow))
            painter.restore()

    def draw_scan_lines(self, painter: QPainter, anim) -> None:
        sy = (anim.time * 120) % self.h
        self.renderer.draw_scan_lines(painter, self.w, self.h, sy, 0.6)

    def draw_vignette(self, painter: QPainter, anim) -> None:
        self.renderer.draw_vignette(painter, self.w, self.h, 0.55)

    def _cam(self, anim, depth: float = 0.3) -> tuple[float, float]:
        cam_x, cam_y = anim.camera_offset
        return self.cx + cam_x * depth, self.cy + cam_y * depth
