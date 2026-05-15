from __future__ import annotations

import json
from typing import Any

from PySide6.QtWidgets import QLabel, QTabWidget, QTextEdit, QVBoxLayout, QWidget

from .agent_graph import AgentGraph
from .memory_network import MemoryNetwork
from .workflow_visualizer import WorkflowVisualizer


class BrainView(QWidget):
    """Zoomed layered view into live cognitive state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.overview = QTextEdit(readOnly=True)
        self.neural = QTextEdit(readOnly=True)
        self.architecture = QTextEdit(readOnly=True)
        self.agent_graph = AgentGraph()
        self.memory_graph = MemoryNetwork()
        self.self_lab = QTextEdit(readOnly=True)
        self.workflow_graph = WorkflowVisualizer()
        self.tabs.addTab(self.overview, "Overview")
        self.tabs.addTab(self.neural, "Neural Activity")
        self.tabs.addTab(self.architecture, "AI OS Layers")
        self.tabs.addTab(self.agent_graph, "Agent Society")
        self.tabs.addTab(self.memory_graph, "Memory Network")
        self.tabs.addTab(self.workflow_graph, "Workflows")
        self.tabs.addTab(self.self_lab, "Self Improvement")
        layout.addWidget(self.tabs)
        self._style()

    def set_snapshot(self, snapshot: dict[str, Any]) -> None:
        snapshot = snapshot or {}
        health = snapshot.get("health", {})
        modules = snapshot.get("modules", [])
        agents = snapshot.get("agents", [])
        workflows = snapshot.get("workflows", [])
        memory = snapshot.get("memory_network", {})
        phase2 = snapshot.get("phase2", {})
        obs = snapshot.get("observability", {})
        self.overview.setPlainText(
            "\n".join(
                [
                    "COGNITIVE OVERVIEW",
                    f"Status: online | Uptime: {snapshot.get('uptime_seconds', 0)}s",
                    f"CPU: {health.get('cpu_percent', 0)}% | RAM: {health.get('memory_percent', 0)}%",
                    f"GPU: {health.get('gpu', {}).get('utilization', 0)}% | CUDA: {health.get('gpu', {}).get('cuda', False)}",
                    f"Modules: {len(modules)} | Failed: {len(health.get('failed_modules', []))}",
                    f"Agents: {len(agents)} | Workflows: {len(workflows)}",
                    f"Memory interactions: {memory.get('interactions', 0)}",
                    f"Phase 2: cnn={phase2.get('cnn_available', False)} rnn={bool(phase2.get('rnn'))}",
                ]
            )
        )
        recent_events = snapshot.get("event_trace", [])[-24:]
        self.neural.setPlainText("\n".join(self._format_event(e) for e in recent_events))
        self.architecture.setPlainText(self._architecture_text(snapshot))
        self.agent_graph.set_snapshot(snapshot)
        self.memory_graph.set_snapshot(snapshot)
        self.workflow_graph.set_snapshot(snapshot)
        self.self_lab.setPlainText(
            json.dumps(
                {
                    "self_improvement": self._module_status(modules, "self_improvement"),
                    "ai_lab": self._module_status(modules, "ai_lab"),
                    "recent_traces": obs.get("traces", [])[:8],
                    "diagnostics": snapshot.get("startup_diagnostics", {}),
                },
                indent=2,
                default=str,
            )
        )

    def _style(self) -> None:
        self.setStyleSheet(
            """
            QTabWidget::pane { border: 1px solid #13233f; background: #050811; }
            QTabBar::tab { background: #0a1122; color: #6080a0; padding: 8px 12px; border: 1px solid #13233f; }
            QTabBar::tab:selected { color: #00d4ff; border-color: #00d4ff; }
            QTextEdit { background: #050811; color: #dff8ff; border: none; font-family: Consolas; font-size: 11px; }
            QLabel { color: #dff8ff; }
            """
        )

    def _format_event(self, item: dict[str, Any]) -> str:
        topic = item.get("topic", "")
        source = item.get("source", "")
        payload = item.get("payload", {})
        return f"{topic:<28} {source:<18} {json.dumps(payload, default=str)[:180]}"

    def _module_status(self, modules: list[dict[str, Any]], name: str) -> dict[str, Any]:
        return next((m for m in modules if m.get("name") == name), {"status": "offline"})

    def _architecture_text(self, snapshot: dict[str, Any]) -> str:
        modules = snapshot.get("modules", [])
        layers = {
            "Interface Layer": ["visual_runtime", "voice_engine"],
            "Cognitive Layer": ["orchestrator", "phase2_deep_learning"],
            "Memory Layer": ["memory"],
            "Automation Layer": ["workflow_engine"],
            "Agent Layer": ["agent_manager", "agent_registry"],
            "AI LAB": ["ai_lab"],
            "Self-Improvement Layer": ["self_improvement"],
        }
        lines = ["AI OS ARCHITECTURE"]
        for layer, names in layers.items():
            statuses = [self._module_status(modules, name).get("status", "offline") for name in names]
            lines.append(f"{layer}: {', '.join(f'{n}={s}' for n, s in zip(names, statuses))}")
        return "\n".join(lines)
