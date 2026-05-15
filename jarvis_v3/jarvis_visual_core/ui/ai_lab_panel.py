from __future__ import annotations

import json
from typing import Any

from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget


class AILabPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.text = QTextEdit(readOnly=True)
        self.text.setStyleSheet("background:#050811;color:#dff8ff;border:1px solid #13233f;font-family:Consolas;")
        layout.addWidget(self.text)

    def set_snapshot(self, snapshot: dict[str, Any]) -> None:
        modules = snapshot.get("modules", [])
        lab = next((m for m in modules if m.get("name") == "ai_lab"), {"status": "offline"})
        improver = next((m for m in modules if m.get("name") == "self_improvement"), {"status": "offline"})
        events = [e for e in snapshot.get("event_trace", []) if "lab" in e.get("topic", "") or "improvement" in e.get("topic", "")]
        self.text.setPlainText(json.dumps({"ai_lab": lab, "self_improvement": improver, "events": events[-20:]}, indent=2, default=str))
