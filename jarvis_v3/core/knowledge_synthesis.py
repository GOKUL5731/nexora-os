"""Autonomous knowledge synthesis across memory, graph, research, and goals."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.advanced_memory import AdvancedMemorySystem
from core.graph_reasoning import GraphReasoningEngine
from core.knowledge_graph import KnowledgeGraph


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "knowledge_synthesis.db"


class KnowledgeSynthesisEngine:
    """Combines multi-domain information into workflow and architecture improvements."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        memory: AdvancedMemorySystem | None = None,
        graph: KnowledgeGraph | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("knowledge_synthesis", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory = memory or AdvancedMemorySystem(self.config)
        self.graph = graph or KnowledgeGraph(self.config)
        self.reasoning = GraphReasoningEngine(self.config, self.graph)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS syntheses (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    sources TEXT NOT NULL,
                    insight TEXT NOT NULL,
                    proposals TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def synthesize(self, topic: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        sources = {
            "episodes": self.memory.recall_episodes(limit=10),
            "runtime_facts": self.memory.list_facts("runtime"),
            "research": self.memory.get_fact("research", topic, default={}),
            "graph_bottlenecks": self.reasoning.bottlenecks(limit=5),
            "graph_opportunities": self.reasoning.optimization_opportunities(),
            "context": context,
        }
        insight = self._build_insight(topic, sources)
        proposals = self.generate_improvements(topic, sources)
        synthesis_id = f"synthesis-{uuid.uuid4().hex[:12]}"
        record = {
            "id": synthesis_id,
            "topic": topic,
            "sources": sources,
            "insight": insight,
            "proposals": proposals,
            "created_at": datetime.now().isoformat(),
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO syntheses VALUES (?,?,?,?,?,?)",
                (
                    synthesis_id,
                    topic,
                    json.dumps(sources, ensure_ascii=False, default=str),
                    insight,
                    json.dumps(proposals, ensure_ascii=False, default=str),
                    record["created_at"],
                ),
            )
        self.memory.store_fact("synthesis", topic, {"insight": insight, "proposals": proposals}, confidence=0.72)
        return record

    def generate_improvements(self, topic: str, sources: dict[str, Any]) -> list[dict[str, Any]]:
        proposals = []
        for opportunity in sources.get("graph_opportunities", []):
            proposals.append(
                {
                    "type": "graph_optimization",
                    "target": opportunity.get("target", topic),
                    "action": opportunity.get("action", "optimize graph structure"),
                    "priority": opportunity.get("priority", 5),
                }
            )
        if sources.get("research"):
            proposals.append({"type": "research_to_workflow", "action": "convert research report into executable workflow", "priority": 6})
        if not proposals:
            proposals.append({"type": "exploration", "action": f"collect more evidence for {topic}", "priority": 3})
        return sorted(proposals, key=lambda item: item["priority"], reverse=True)

    def list_syntheses(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,topic,sources,insight,proposals,created_at FROM syntheses ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "topic": row[1],
                "sources": json.loads(row[2] or "{}"),
                "insight": row[3],
                "proposals": json.loads(row[4] or "[]"),
                "created_at": row[5],
            }
            for row in rows
        ]

    @staticmethod
    def _build_insight(topic: str, sources: dict[str, Any]) -> str:
        episodes = len(sources.get("episodes", []))
        bottlenecks = len(sources.get("graph_bottlenecks", []))
        opportunities = len(sources.get("graph_opportunities", []))
        return (
            f"Synthesis for {topic}: {episodes} recent episodes, "
            f"{bottlenecks} graph bottlenecks, and {opportunities} optimization opportunities were combined."
        )
