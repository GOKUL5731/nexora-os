from __future__ import annotations

import math
import time
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


CYAN = QColor("#00d4ff")
BLUE = QColor("#2979ff")
GREEN = QColor("#00ff9d")
WARN = QColor("#ffb020")
RED = QColor("#ff4d6d")
BG = QColor("#050811")


class CognitiveOrb(QWidget):
    """Live visual model of the JARVIS cognitive core."""

    zoom_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(460, 460)
        self.snapshot: dict[str, Any] = {}
        self.angle = 0.0
        self.last_event_count = 0
        self.activity = 0.05
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    def set_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = snapshot or {}
        events = self.snapshot.get("event_trace", [])
        event_count = len(events)
        delta = max(0, event_count - self.last_event_count)
        self.last_event_count = event_count
        audio = self.snapshot.get("audio", {}).get("level", 0.0)
        task = self.snapshot.get("current_task", {})
        workflows = self.snapshot.get("running_workflows", [])
        agents = [a for a in self.snapshot.get("agents", []) if a.get("status") == "running"]
        target = min(1.0, audio + delta * 0.05 + len(workflows) * 0.15 + len(agents) * 0.12)
        if task.get("status") in {"started", "executing", "planning"}:
            target = max(target, 0.45)
        self.activity = self.activity * 0.82 + target * 0.18

    def _tick(self) -> None:
        self.angle = (self.angle + 0.65 + self.activity * 2.0) % 360
        self.update()

    def mouseDoubleClickEvent(self, event):
        self.zoom_requested.emit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), BG)

        center = QPointF(self.width() / 2, self.height() / 2 - 8)
        radius = min(self.width(), self.height()) * 0.28
        activity = max(0.02, min(1.0, self.activity))

        glow = QRadialGradient(center, radius * (2.3 + activity))
        g0 = QColor(CYAN)
        g0.setAlpha(80 + int(activity * 80))
        g1 = QColor(BLUE)
        g1.setAlpha(35)
        glow.setColorAt(0.0, g0)
        glow.setColorAt(0.45, g1)
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), glow)

        self._draw_streams(painter, center, radius, activity)
        self._draw_rings(painter, center, radius, activity)
        self._draw_nodes(painter, center, radius)
        self._draw_labels(painter, center, radius)
        painter.end()

    def _draw_rings(self, painter: QPainter, center: QPointF, radius: float, activity: float) -> None:
        painter.save()
        painter.translate(center)
        for index, scale in enumerate([1.0, 1.28, 1.56]):
            painter.save()
            painter.rotate(self.angle * (1 if index != 1 else -0.7) + index * 18)
            color = [CYAN, BLUE, GREEN][index]
            color = QColor(color)
            color.setAlpha(120 + int(activity * 90))
            pen = QPen(color, 1.5 + index * 0.5)
            if index != 0:
                pen.setDashPattern([12 - index * 2, 8 + index * 2])
            painter.setPen(pen)
            r = radius * scale
            painter.drawEllipse(QRectF(-r, -r, r * 2, r * 2))
            painter.restore()
        painter.restore()

    def _draw_streams(self, painter: QPainter, center: QPointF, radius: float, activity: float) -> None:
        events = self.snapshot.get("event_trace", [])[-18:]
        if not events:
            return
        now = time.time()
        painter.save()
        for idx, item in enumerate(events):
            age = max(0.0, now - float(item.get("timestamp", now)))
            alpha = max(25, 190 - int(age * 55))
            source_angle = (idx * 137.5 + self.angle) % 360
            a = math.radians(source_angle)
            start = QPointF(center.x() + math.cos(a) * radius * 2.0, center.y() + math.sin(a) * radius * 2.0)
            end = QPointF(center.x() + math.cos(a + 2.2) * radius * 0.35, center.y() + math.sin(a + 2.2) * radius * 0.35)
            c1 = QPointF((start.x() + center.x()) / 2, start.y())
            c2 = QPointF(center.x(), (end.y() + center.y()) / 2)
            path = QPainterPath(start)
            path.cubicTo(c1, c2, end)
            color = self._topic_color(item.get("topic", ""))
            color.setAlpha(alpha)
            painter.setPen(QPen(color, 1.2 + activity * 2.0))
            painter.drawPath(path)
        painter.restore()

    def _draw_nodes(self, painter: QPainter, center: QPointF, radius: float) -> None:
        agents = self.snapshot.get("agents", [])[:8]
        workflows = self.snapshot.get("workflows", [])[:6]
        modules = self.snapshot.get("modules", [])[:8]
        counts = [("Agents", len(agents), GREEN), ("Flows", len(workflows), CYAN), ("Modules", len(modules), BLUE)]
        painter.save()
        painter.setFont(QFont("Segoe UI", 8))
        for idx, (label, count, color) in enumerate(counts):
            a = math.radians(idx * 120 - 90 + self.angle * 0.12)
            p = QPointF(center.x() + math.cos(a) * radius * 1.82, center.y() + math.sin(a) * radius * 1.82)
            c = QColor(color)
            c.setAlpha(190)
            painter.setPen(QPen(c, 1))
            painter.setBrush(QColor(5, 8, 17, 180))
            painter.drawEllipse(p, 26, 26)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(p.x() - 26, p.y() - 13, 52, 18), Qt.AlignCenter, str(count))
            painter.setPen(c)
            painter.drawText(QRectF(p.x() - 44, p.y() + 10, 88, 18), Qt.AlignCenter, label)
        painter.restore()

    def _draw_labels(self, painter: QPainter, center: QPointF, radius: float) -> None:
        health = self.snapshot.get("health", {})
        failed = len(health.get("failed_modules", []))
        task = self.snapshot.get("current_task", {})
        voice = self.snapshot.get("voice", {})
        status = task.get("status") or voice.get("status") or "online"

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Consolas", 22, QFont.Bold))
        painter.drawText(QRectF(center.x() - radius, center.y() - 26, radius * 2, 32), Qt.AlignCenter, "JARVIS")
        color = RED if failed else CYAN
        painter.setPen(color)
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(QRectF(center.x() - radius * 1.5, center.y() + 12, radius * 3, 22), Qt.AlignCenter, status.replace("_", " ").upper())

    def _topic_color(self, topic: str) -> QColor:
        if topic.startswith("agent."):
            return QColor(GREEN)
        if topic.startswith("workflow."):
            return QColor(CYAN)
        if topic.startswith("voice.") or topic.startswith("audio."):
            return QColor(BLUE)
        if "failed" in topic or "error" in topic:
            return QColor(RED)
        if topic.startswith("memory."):
            return QColor("#b2ff59")
        return QColor("#8ab4ff")
