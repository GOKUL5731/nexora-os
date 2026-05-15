"""Real runtime debug dashboard.

This panel is intentionally plain: it displays actual backend state from the
event bus, module manager, health monitor, and async runtime. It does not
simulate activity.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.event_bus import get_event_bus
from core.health_monitor import HealthMonitor
from core.module_manager import get_module_manager


class DebugDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = get_event_bus()
        self.modules = get_module_manager()
        self.health = HealthMonitor(bus=self.bus, modules=self.modules)
        self._build()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        self.summary = QLabel("Runtime state unavailable")
        layout.addWidget(self.summary)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.modules_table = QTableWidget(0, 5)
        self.modules_table.setHorizontalHeaderLabels(["Module", "Status", "Detail", "Error", "Updated"])
        self.events = QTextEdit(readOnly=True)
        self.threads = QTextEdit(readOnly=True)
        self.workflows = QTextEdit(readOnly=True)
        self.agents = QTextEdit(readOnly=True)
        self.raw = QTextEdit(readOnly=True)

        self.tabs.addTab(self.modules_table, "Modules")
        self.tabs.addTab(self.events, "Events")
        self.tabs.addTab(self.threads, "Threads")
        self.tabs.addTab(self.workflows, "Workflows")
        self.tabs.addTab(self.agents, "Agents")
        self.tabs.addTab(self.raw, "Raw Health")

    def refresh(self) -> None:
        snap = self.health.snapshot()
        self.summary.setText(
            f"CPU {snap.get('cpu_percent', 0)}% | "
            f"RAM {snap.get('memory_percent', 0)}% | "
            f"GPU {snap.get('gpu', {}).get('utilization', 0)}% | "
            f"Modules {len(snap.get('modules', {}))} | "
            f"Failed {len(snap.get('failed_modules', []))} | "
            f"Event errors {snap.get('event_bus', {}).get('subscriber_error_count', 0)}"
        )
        self._update_modules(snap.get("modules", {}))
        self.events.setPlainText("\n".join(self._format_event(e) for e in self.bus.history(limit=120)))
        self.threads.setPlainText(json.dumps(snap.get("threads", {}), indent=2, default=str))
        self.workflows.setPlainText(json.dumps({
            "queue": snap.get("workflow_queue", {}),
            "workflows": snap.get("workflows", []),
        }, indent=2, default=str))
        self.agents.setPlainText(json.dumps(snap.get("agents", []), indent=2, default=str))
        self.raw.setPlainText(json.dumps(snap, indent=2, default=str))

    def _update_modules(self, modules: dict[str, Any]) -> None:
        rows = list(modules.values()) if isinstance(modules, dict) else list(modules or [])
        self.modules_table.setRowCount(len(rows))
        for row, module in enumerate(rows):
            values = [
                module.get("name", ""),
                module.get("status", ""),
                module.get("detail", ""),
                module.get("error", ""),
                str(module.get("updated_at", "")),
            ]
            for col, value in enumerate(values):
                self.modules_table.setItem(row, col, QTableWidgetItem(str(value)))

    def _format_event(self, event) -> str:
        payload = json.dumps(event.payload, default=str)[:240]
        return f"{event.sequence:06d} {event.topic:<32} {event.source:<20} {payload}"
