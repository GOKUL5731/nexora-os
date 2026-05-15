"""Graph validation and reasoning helpers for planning and optimization."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from core.knowledge_graph import KnowledgeGraph


class GraphReasoningEngine:
    """Runs lightweight reasoning over the persistent knowledge graph."""

    def __init__(self, config: dict | None = None, graph: KnowledgeGraph | None = None):
        self.config = config or {}
        self.graph = graph or KnowledgeGraph(self.config)

    def validate(self) -> dict[str, Any]:
        snapshot = self.graph.snapshot(limit=5000)
        node_ids = {node["id"] for node in snapshot["nodes"]}
        dangling = [
            edge for edge in snapshot["edges"] if edge["source"] not in node_ids or edge["target"] not in node_ids
        ]
        cycles = self.detect_cycles(snapshot)
        return {"valid": not dangling, "dangling_edges": dangling[:50], "cycles": cycles[:20]}

    def detect_cycles(self, snapshot: dict[str, Any] | None = None) -> list[list[str]]:
        snapshot = snapshot or self.graph.snapshot(limit=5000)
        graph: dict[str, list[str]] = defaultdict(list)
        for edge in snapshot["edges"]:
            if edge["relation"] in {"precedes", "depends_on"}:
                graph[edge["source"]].append(edge["target"])
        cycles = []
        path: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def dfs(node: str) -> None:
            if node in visiting:
                if node in path:
                    cycles.append(path[path.index(node) :] + [node])
                return
            if node in visited:
                return
            visiting.add(node)
            path.append(node)
            for nxt in graph.get(node, []):
                dfs(nxt)
            path.pop()
            visiting.remove(node)
            visited.add(node)

        for node in list(graph):
            dfs(node)
        return cycles

    def shortest_path(self, source: str, target: str) -> list[str]:
        snapshot = self.graph.snapshot(limit=5000)
        adjacency: dict[str, list[str]] = defaultdict(list)
        for edge in snapshot["edges"]:
            adjacency[edge["source"]].append(edge["target"])
        queue = deque([(source, [source])])
        seen = {source}
        while queue:
            node, path = queue.popleft()
            if node == target:
                return path
            for nxt in adjacency.get(node, []):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, path + [nxt]))
        return []

    def bottlenecks(self, limit: int = 10) -> list[dict[str, Any]]:
        snapshot = self.graph.snapshot(limit=5000)
        degree: dict[str, dict[str, int]] = defaultdict(lambda: {"in": 0, "out": 0})
        labels = {node["id"]: node for node in snapshot["nodes"]}
        for edge in snapshot["edges"]:
            degree[edge["source"]]["out"] += 1
            degree[edge["target"]]["in"] += 1
        ranked = sorted(
            (
                {
                    "id": node_id,
                    "label": labels.get(node_id, {}).get("label", node_id),
                    "type": labels.get(node_id, {}).get("type", "unknown"),
                    "in": counts["in"],
                    "out": counts["out"],
                    "score": counts["in"] + counts["out"],
                }
                for node_id, counts in degree.items()
            ),
            key=lambda item: item["score"],
            reverse=True,
        )
        return ranked[:limit]

    def optimization_opportunities(self) -> list[dict[str, Any]]:
        opportunities = []
        validation = self.validate()
        if validation["dangling_edges"]:
            opportunities.append({"type": "graph_integrity", "action": "repair dangling edges", "priority": 9})
        if validation["cycles"]:
            opportunities.append({"type": "dependency_cycle", "action": "break cyclic dependencies", "priority": 10})
        for node in self.bottlenecks(limit=5):
            if node["score"] >= 5:
                opportunities.append(
                    {
                        "type": "bottleneck",
                        "target": node["id"],
                        "action": "cache or split highly connected workflow element",
                        "priority": min(9, 4 + node["score"]),
                    }
                )
        return sorted(opportunities, key=lambda item: item["priority"], reverse=True)
