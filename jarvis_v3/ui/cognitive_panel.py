"""Cognitive state panel helpers for the autonomous layer."""

from __future__ import annotations

from typing import Any


class CognitiveStateModel:
    """UI-friendly adapter for active planning, memory, and reasoning state."""

    def __init__(self, orchestration_engine: Any = None):
        self.engine = orchestration_engine

    async def snapshot(self) -> dict[str, Any]:
        if not self.engine:
            return {"status": "offline"}
        tick = await self.engine.cognitive_tick()
        graph = self.engine.graph.snapshot(limit=80)
        return {
            "reasoning_mode": tick.get("context", {}).get("task_mode", "general"),
            "memory_retrieval": self.engine.memory.recall_episodes(limit=5),
            "predictions": tick.get("predictions", {}),
            "suggestions": tick.get("suggestions", []),
            "planning_tree": graph,
        }


try:
    import asyncio
    import json
    from PySide6.QtCore import QThread, QTimer, Signal
    from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

    class _SnapshotWorker(QThread):
        done = Signal(dict)

        def __init__(self, model: CognitiveStateModel):
            super().__init__()
            self.model = model

        def run(self) -> None:
            loop = asyncio.new_event_loop()
            try:
                self.done.emit(loop.run_until_complete(self.model.snapshot()))
            finally:
                loop.close()

    class CognitiveStatePanel(QWidget):
        def __init__(self, model: CognitiveStateModel, parent=None):
            super().__init__(parent)
            self.model = model
            self.worker = None
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("COGNITIVE STATE"))
            self.output = QTextEdit()
            self.output.setReadOnly(True)
            layout.addWidget(self.output)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.refresh)
            self.timer.start(5000)
            self.refresh()

        def refresh(self) -> None:
            if self.worker and self.worker.isRunning():
                return
            self.worker = _SnapshotWorker(self.model)
            self.worker.done.connect(lambda data: self.output.setPlainText(json.dumps(data, indent=2, default=str)))
            self.worker.start()

except Exception:
    CognitiveStatePanel = None
