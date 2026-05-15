from __future__ import annotations

import asyncio
import json
from typing import Any

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .agent_graph import AgentGraph
from .ai_lab_panel import AILabPanel
from .brain_view import BrainView
from .cognitive_orb import CognitiveOrb
from .diagnostics_panel import DiagnosticsPanel
from .memory_network import MemoryNetwork
from .workflow_visualizer import WorkflowVisualizer


class RuntimeCommandWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, runtime, command: str):
        super().__init__()
        self.runtime = runtime
        self.command = command

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.runtime.process_command(self.command))
            self.done.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            loop.close()


class OrchestrationDashboard(QMainWindow):
    """Cinematic but state-real JARVIS visual operating dashboard."""

    def __init__(self, runtime, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.snapshot: dict[str, Any] = {}
        self.workers: list[QThread] = []
        self.setWindowTitle("JARVIS CORE OS - Visual Runtime")
        self.resize(1500, 900)
        self._setup_palette()
        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(500)
        self.refresh()

    def _setup_palette(self) -> None:
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor("#050811"))
        pal.setColor(QPalette.WindowText, QColor("#ffffff"))
        self.setPalette(pal)
        self.setStyleSheet(
            """
            QWidget { background:#050811; color:#ffffff; font-family:Segoe UI; }
            QFrame[panel="true"] { background:#0a1122; border:1px solid #13233f; border-radius:8px; }
            QPushButton { background:#07101f; color:#9ecfff; border:1px solid #13233f; border-radius:6px; padding:9px; text-align:left; }
            QPushButton:hover { border-color:#00d4ff; color:#00d4ff; }
            QLineEdit, QTextEdit, QListWidget { background:#050811; color:#dff8ff; border:1px solid #13233f; border-radius:6px; padding:8px; }
            """
        )

    def _build(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QGridLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.nav = self._nav()
        self.stack = QStackedWidget()
        self.right = self._right_panel()
        self.console = self._console_panel()

        layout.addWidget(self.nav, 0, 0, 2, 1)
        layout.addWidget(self.stack, 0, 1, 1, 1)
        layout.addWidget(self.right, 0, 2, 2, 1)
        layout.addWidget(self.console, 1, 1, 1, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(0, 2)
        layout.setRowStretch(1, 1)

        self.home = CognitiveOrb()
        self.home.zoom_requested.connect(lambda: self._select("Brain"))
        self.brain = BrainView()
        self.agents = AgentGraph()
        self.workflows = WorkflowVisualizer()
        self.memory = MemoryNetwork()
        self.automation = WorkflowVisualizer()
        self.vision = DiagnosticsPanel()
        self.ai_lab = AILabPanel()
        self.settings = DiagnosticsPanel()

        for name, widget in [
            ("Home", self.home),
            ("Brain", self.brain),
            ("Agents", self.agents),
            ("Workflows", self.workflows),
            ("Memory", self.memory),
            ("Automation", self.automation),
            ("Vision", self.vision),
            ("AI LAB", self.ai_lab),
            ("Settings", self.settings),
        ]:
            self.stack.addWidget(widget)

    def _nav(self) -> QFrame:
        frame = QFrame()
        frame.setProperty("panel", True)
        frame.setFixedWidth(170)
        layout = QVBoxLayout(frame)
        title = QLabel("JARVIS\nCORE OS")
        title.setStyleSheet("color:#00d4ff;font-size:18px;font-weight:700;")
        layout.addWidget(title)
        self.nav_buttons = {}
        for index, name in enumerate(["Home", "Brain", "Agents", "Workflows", "Memory", "Automation", "Vision", "AI LAB", "Settings"]):
            btn = QPushButton(name)
            btn.clicked.connect(lambda _checked=False, i=index, n=name: self._select(n))
            self.nav_buttons[name] = btn
            layout.addWidget(btn)
        layout.addStretch()
        return frame

    def _right_panel(self) -> QFrame:
        frame = QFrame()
        frame.setProperty("panel", True)
        frame.setFixedWidth(310)
        layout = QVBoxLayout(frame)
        title = QLabel("LIVE SYSTEM STATE")
        title.setStyleSheet("color:#00d4ff;font-weight:700;")
        layout.addWidget(title)
        self.state_labels = {}
        for key in ["CPU", "GPU", "RAM", "Models", "Agents", "Workflows", "Modules", "Voice"]:
            label = QLabel(f"{key}: --")
            label.setStyleSheet("color:#dff8ff;padding:4px;")
            self.state_labels[key] = label
            layout.addWidget(label)
        layout.addWidget(QLabel("ACTIVE MODULES"))
        self.modules_list = QListWidget()
        layout.addWidget(self.modules_list, 1)
        return frame

    def _console_panel(self) -> QFrame:
        frame = QFrame()
        frame.setProperty("panel", True)
        layout = QVBoxLayout(frame)
        title = QLabel("LIVE COMMAND CONSOLE")
        title.setStyleSheet("color:#00d4ff;font-weight:700;")
        self.console_view = QTextEdit(readOnly=True)
        cmd_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Type a JARVIS command...")
        self.command_input.returnPressed.connect(self._run_command)
        run = QPushButton("Run")
        run.clicked.connect(self._run_command)
        cmd_row.addWidget(self.command_input, 1)
        cmd_row.addWidget(run)
        layout.addWidget(title)
        layout.addWidget(self.console_view, 1)
        layout.addLayout(cmd_row)
        return frame

    def _select(self, name: str) -> None:
        names = list(self.nav_buttons)
        if name in names:
            self.stack.setCurrentIndex(names.index(name))

    def refresh(self) -> None:
        self.snapshot = self.runtime.snapshot()
        self.home.set_snapshot(self.snapshot)
        self.brain.set_snapshot(self.snapshot)
        self.agents.set_snapshot(self.snapshot)
        self.workflows.set_snapshot(self.snapshot)
        self.memory.set_snapshot(self.snapshot)
        self.automation.set_snapshot(self.snapshot)
        self.vision.set_snapshot(self.snapshot)
        self.ai_lab.set_snapshot(self.snapshot)
        self.settings.set_snapshot(self.snapshot)
        self._update_right_panel()
        self._update_console()

    def _update_right_panel(self) -> None:
        health = self.snapshot.get("health", {})
        gpu = health.get("gpu", {})
        self.state_labels["CPU"].setText(f"CPU: {health.get('cpu_percent', 0)}%")
        self.state_labels["GPU"].setText(f"GPU: {gpu.get('utilization', 0)}% | {gpu.get('name', 'N/A')}")
        self.state_labels["RAM"].setText(f"RAM: {health.get('memory_percent', 0)}%")
        self.state_labels["Models"].setText(f"Models: {len(self.snapshot.get('startup_diagnostics', {}).get('models', []))}")
        self.state_labels["Agents"].setText(f"Agents: {len(self.snapshot.get('agents', []))}")
        self.state_labels["Workflows"].setText(f"Workflows: {len(self.snapshot.get('workflows', []))}")
        failed = len(health.get("failed_modules", []))
        self.state_labels["Modules"].setText(f"Modules: {len(self.snapshot.get('modules', []))} | Failed: {failed}")
        self.state_labels["Voice"].setText(f"Voice: {self.snapshot.get('voice', {}).get('status', 'idle')}")
        self.modules_list.clear()
        for module in self.snapshot.get("modules", []):
            item = QListWidgetItem(f"{module.get('name')}  [{module.get('status')}]")
            if module.get("status") in {"failed", "error"}:
                item.setForeground(QColor("#ff4d6d"))
            elif module.get("status") in {"online", "degraded"}:
                item.setForeground(QColor("#00d4ff"))
            self.modules_list.addItem(item)

    def _update_console(self) -> None:
        events = self.snapshot.get("event_trace", [])[-80:]
        lines = []
        for event in events:
            payload = event.get("payload", {})
            message = payload.get("message") or payload.get("raw_message") or json.dumps(payload, default=str)[:120]
            lines.append(f"{event.get('topic'):<28} {message}")
        current = "\n".join(lines)
        if self.console_view.toPlainText() != current:
            self.console_view.setPlainText(current)
            self.console_view.moveCursor(self.console_view.textCursor().MoveOperation.End)

    def _run_command(self) -> None:
        command = self.command_input.text().strip()
        if not command:
            return
        self.command_input.clear()
        worker = RuntimeCommandWorker(self.runtime, command)
        worker.done.connect(lambda result, w=worker: self._command_done(w, result))
        worker.error.connect(lambda error, w=worker: self._command_error(w, error))
        self.workers.append(worker)
        worker.start()

    def _command_done(self, worker, result: dict) -> None:
        self.runtime.bus.publish("console.response", result, source="visual_dashboard")
        self._cleanup_worker(worker)

    def _command_error(self, worker, error: str) -> None:
        self.runtime.bus.publish("console.error", {"message": error}, source="visual_dashboard")
        self._cleanup_worker(worker)

    def _cleanup_worker(self, worker) -> None:
        if worker in self.workers:
            self.workers.remove(worker)

    def closeEvent(self, event) -> None:
        for worker in list(self.workers):
            if worker.isRunning():
                worker.quit()
                worker.wait(1000)
        super().closeEvent(event)
