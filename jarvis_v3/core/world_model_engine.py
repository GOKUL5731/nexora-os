"""Unified world model backed by the real-time knowledge graph."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

import psutil

from core.knowledge_graph import KnowledgeGraph


class WorldModelEngine:
    """Maintains device, workflow, user, app, plugin, and goal relationships."""

    def __init__(self, config: dict | None = None, graph: KnowledgeGraph | None = None):
        self.config = config or {}
        self.graph = graph or KnowledgeGraph(self.config)

    def observe_system(self) -> dict[str, Any]:
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        device = {
            "platform": platform.platform(),
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": vm.percent,
            "memory_total_gb": round(vm.total / (1024 ** 3), 2),
            "disk_percent": disk.percent,
        }
        self.graph.upsert_node("device:local", "device", platform.node() or "local-device", device)
        self.graph.upsert_node("resource:cpu", "resource", "CPU", {"percent": device["cpu_percent"]})
        self.graph.upsert_node("resource:memory", "resource", "Memory", {"percent": device["memory_percent"]})
        self.graph.connect("device:local", "resource:cpu", "has_resource")
        self.graph.connect("device:local", "resource:memory", "has_resource")
        return device

    def update_user_context(self, user_id: str, context: dict[str, Any]) -> None:
        node = f"user:{user_id}"
        self.graph.upsert_node(node, "user", user_id, context)
        for action in context.get("recent_actions", []):
            action_id = f"action:{str(action.get('action', action))[:80]}"
            self.graph.upsert_node(action_id, "user_action", str(action.get("action", action)), action)
            self.graph.connect(node, action_id, "performed")

    def update_plugin_map(self, plugins: list[dict[str, Any]] | None = None, plugin_root: str | Path | None = None) -> None:
        plugins = plugins or []
        if plugin_root:
            root = Path(plugin_root)
            if root.exists():
                for path in root.iterdir():
                    if path.is_dir():
                        plugins.append({"name": path.name, "path": str(path)})
        for plugin in plugins:
            plugin_id = f"plugin:{plugin.get('name', 'unnamed')}"
            self.graph.upsert_node(plugin_id, "plugin", plugin.get("name", "unnamed"), plugin)
            for dep in plugin.get("dependencies", []):
                dep_id = f"dependency:{dep}"
                self.graph.upsert_node(dep_id, "dependency", dep, {})
                self.graph.connect(plugin_id, dep_id, "depends_on")

    def update_workflow_map(self, workflows: list[dict[str, Any]]) -> None:
        for workflow in workflows:
            self.graph.ingest_workflow(workflow)

    def update_goal_map(self, goals: list[dict[str, Any]]) -> None:
        for goal in goals:
            goal_id = goal["id"]
            self.graph.upsert_node(goal_id, "goal", goal["title"], goal)
            for dep in goal.get("dependencies", []):
                self.graph.connect(goal_id, dep, "depends_on")

    def infer_next_context(self) -> dict[str, Any]:
        snapshot = self.graph.snapshot(limit=300)
        node_types: dict[str, int] = {}
        relation_counts: dict[str, int] = {}
        for node in snapshot["nodes"]:
            node_types[node["type"]] = node_types.get(node["type"], 0) + 1
        for edge in snapshot["edges"]:
            relation_counts[edge["relation"]] = relation_counts.get(edge["relation"], 0) + 1
        return {
            "node_types": node_types,
            "relation_counts": relation_counts,
            "probable_focus": self._probable_focus(snapshot),
        }

    def snapshot(self, limit: int = 200) -> dict[str, Any]:
        data = self.graph.snapshot(limit=limit)
        data["inference"] = self.infer_next_context()
        return data

    @staticmethod
    def _probable_focus(snapshot: dict[str, Any]) -> str:
        for preferred in ("goal", "plan", "workflow", "plugin"):
            if any(node["type"] == preferred for node in snapshot.get("nodes", [])):
                return preferred
        return "system"
