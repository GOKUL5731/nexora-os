from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class WorkflowVisualizer(QWidget):
    """Live node view of workflows and current execution state."""

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
        workflows = self.snapshot.get("workflows", [])
        running = set(self.snapshot.get("running_workflows", []))
        if not workflows:
            painter.setPen(QColor("#6080a0"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No workflows installed")
            return
        x = 24
        y = 32
        for workflow in workflows[:5]:
            actions = workflow.get("actions", []) or ["manual_trigger"]
            name = workflow.get("name", "workflow")
            color = QColor("#ffb020" if name in running else "#00d4ff")
            painter.setPen(color)
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(QRectF(x, y - 22, self.width() - 48, 18), Qt.AlignLeft, name)
            last_rect = None
            for idx, action in enumerate(actions[:7]):
                rect = QRectF(x + idx * 118, y, 94, 32)
                if last_rect:
                    self._draw_edge(painter, last_rect, rect, color)
                painter.setBrush(QColor("#0a1122"))
                painter.setPen(QPen(color, 1))
                painter.drawRoundedRect(rect, 4, 4)
                painter.setPen(QColor("#ffffff"))
                painter.setFont(QFont("Segoe UI", 7))
                painter.drawText(rect, Qt.AlignCenter, action.replace("_", " "))
                last_rect = rect
            y += 76

    def _draw_edge(self, painter: QPainter, a: QRectF, b: QRectF, color: QColor) -> None:
        p1 = a.center()
        p1.setX(a.right())
        p2 = b.center()
        p2.setX(b.left())
        path = QPainterPath(p1)
        c1 = p1
        c1.setX(p1.x() + 20)
        c2 = p2
        c2.setX(p2.x() - 20)
        path.cubicTo(c1, c2, p2)
        painter.setPen(QPen(color, 1))
        painter.drawPath(path)
