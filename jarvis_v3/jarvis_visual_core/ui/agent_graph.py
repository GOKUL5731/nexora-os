from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class AgentGraph(QWidget):
    """Live agent society graph driven by AgentManager state and bus events."""

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
        agents = self.snapshot.get("agents", [])
        if not agents:
            painter.setPen(QColor("#6080a0"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Agent runtime offline")
            return
        positions = self._positions(len(agents))
        events = self.snapshot.get("event_trace", [])[-80:]
        active_pairs = []
        for item in events:
            payload = item.get("payload", {})
            if item.get("topic") == "agent.message":
                active_pairs.append((payload.get("from"), payload.get("to")))
            elif item.get("topic", "").startswith("agent."):
                active_pairs.append(("commander", payload.get("agent")))

        name_to_pos = {agent.get("name"): positions[i] for i, agent in enumerate(agents)}
        painter.setPen(QPen(QColor("#13233f"), 1))
        names = list(name_to_pos)
        for i, src in enumerate(names):
            for dst in names[i + 1:]:
                self._draw_connection(painter, name_to_pos[src], name_to_pos[dst], QColor("#13233f"), 1)
        for src, dst in active_pairs[-18:]:
            if src in name_to_pos and dst in name_to_pos:
                self._draw_connection(painter, name_to_pos[src], name_to_pos[dst], QColor("#00d4ff"), 2)

        for agent, pos in zip(agents, positions):
            status = agent.get("status", "idle")
            color = QColor("#00ff9d" if status == "idle" else "#ffb020" if status == "running" else "#ff4d6d")
            painter.setBrush(QColor("#0a1122"))
            painter.setPen(QPen(color, 2))
            painter.drawEllipse(pos, 34, 34)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.drawText(QRectF(pos.x() - 48, pos.y() - 10, 96, 18), Qt.AlignCenter, agent.get("name", "agent"))
            painter.setPen(color)
            painter.setFont(QFont("Segoe UI", 7))
            painter.drawText(QRectF(pos.x() - 48, pos.y() + 10, 96, 18), Qt.AlignCenter, status)

    def _positions(self, count: int) -> list[QPointF]:
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = max(70, min(self.width(), self.height()) * 0.34)
        return [
            QPointF(center.x() + math.cos(2 * math.pi * i / count - math.pi / 2) * radius,
                    center.y() + math.sin(2 * math.pi * i / count - math.pi / 2) * radius)
            for i in range(count)
        ]

    def _draw_connection(self, painter: QPainter, a: QPointF, b: QPointF, color: QColor, width: int) -> None:
        path = QPainterPath(a)
        mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2 - 24)
        path.quadTo(mid, b)
        painter.setPen(QPen(color, width))
        painter.drawPath(path)
