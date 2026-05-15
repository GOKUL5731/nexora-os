"""Workflow analytics panel helpers for the autonomous layer."""

from __future__ import annotations

from typing import Any


class WorkflowAnalyticsModel:
    """UI-friendly analytics adapter around WorkflowGenerator and WorkflowEngine."""

    def __init__(self, workflow_generator: Any = None, workflow_engine: Any = None):
        self.workflow_generator = workflow_generator
        self.workflow_engine = workflow_engine

    def snapshot(self) -> dict[str, Any]:
        generated = self.workflow_generator.analytics() if self.workflow_generator else {}
        workflows = self.workflow_engine.list_workflows() if self.workflow_engine else []
        bottlenecks = []
        for workflow in workflows:
            if workflow.get("last_status") not in {"success", "never"}:
                bottlenecks.append(
                    {
                        "workflow": workflow.get("name"),
                        "status": workflow.get("last_status"),
                        "run_count": workflow.get("run_count", 0),
                    }
                )
        return {"generated": generated, "workflows": workflows, "bottlenecks": bottlenecks}


try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

    class WorkflowAnalyticsPanel(QWidget):
        def __init__(self, model: WorkflowAnalyticsModel, parent=None):
            super().__init__(parent)
            self.model = model
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("WORKFLOW ANALYTICS"))
            self.output = QTextEdit()
            self.output.setReadOnly(True)
            layout.addWidget(self.output)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.refresh)
            self.timer.start(3000)
            self.refresh()

        def refresh(self) -> None:
            import json

            self.output.setPlainText(json.dumps(self.model.snapshot(), indent=2, default=str))

except Exception:
    WorkflowAnalyticsPanel = None
