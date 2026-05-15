from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class MemoryNetwork(QWidget):
    """Visualizes actual stored memory counts and recent retrieval/event paths."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(260)
        self.snapshot: dict[str, Any] = {}

    def set_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = snapshot or {}
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#050811"))
        memory = self.snapshot.get("memory_network", {})
        recent = memory.get("recent_events", [])
        prefs = memory.get("preferences", {})
        interaction_count = memory.get("interactions", 0)
        nodes = [
            ("Episodic", len(recent), "#00d4ff"),
            ("Semantic", len(prefs), "#b2ff59"),
            ("Procedural", len(self.snapshot.get("tools", [])), "#2979ff"),
            ("Vector", interaction_count, "#00ff9d"),
        ]
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) * 0.32
        positions = []
        for i, _node in enumerate(nodes):
            a = math.radians(i * 90 - 45)
            positions.append(QPointF(center.x() + math.cos(a) * radius, center.y() + math.sin(a) * radius))
        for i, p in enumerate(positions):
            painter.setPen(QPen(QColor("#13233f"), 1))
            painter.drawLine(center, p)
        painter.setBrush(QColor("#0a1122"))
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawEllipse(center, 42, 42)
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(QRectF(center.x() - 46, center.y() - 10, 92, 22), Qt.AlignCenter, "Memory")
        for (label, count, color), p in zip(nodes, positions):
            c = QColor(color)
            painter.setPen(QPen(c, 2))
            painter.setBrush(QColor("#0a1122"))
            painter.drawEllipse(p, 42, 42)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(p.x() - 50, p.y() - 13, 100, 18), Qt.AlignCenter, label)
            painter.setPen(c)
            painter.drawText(QRectF(p.x() - 50, p.y() + 5, 100, 18), Qt.AlignCenter, str(count))
