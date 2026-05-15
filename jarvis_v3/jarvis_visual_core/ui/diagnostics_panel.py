from __future__ import annotations

import json
from typing import Any

from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget


class DiagnosticsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.text = QTextEdit(readOnly=True)
        self.text.setStyleSheet("background:#050811;color:#dff8ff;border:1px solid #13233f;font-family:Consolas;")
        layout.addWidget(self.text)

    def set_snapshot(self, snapshot: dict[str, Any]) -> None:
        health = snapshot.get("health", {})
        diagnostics = snapshot.get("startup_diagnostics", {})
        self.text.setPlainText(
            json.dumps(
                {
                    "startup": diagnostics,
                    "health": health,
                    "recent_events": snapshot.get("event_trace", [])[-20:],
                },
                indent=2,
                default=str,
            )
        )
