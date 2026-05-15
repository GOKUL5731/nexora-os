"""Autonomous knowledge discovery loops for missing knowledge and procedure synthesis."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.autonomous_research import AutonomousResearchEngine
from core.knowledge_synthesis import KnowledgeSynthesisEngine


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "knowledge_discovery.db"


class KnowledgeDiscoveryEngine:
    """Identifies knowledge gaps, researches them, verifies findings, and synthesizes procedures."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        research: AutonomousResearchEngine | None = None,
        synthesis: KnowledgeSynthesisEngine | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("knowledge_discovery", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.research = research or AutonomousResearchEngine(self.config)
        self.synthesis = synthesis or KnowledgeSynthesisEngine(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS discoveries (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    gap TEXT NOT NULL,
                    research TEXT DEFAULT '{}',
                    synthesis TEXT DEFAULT '{}',
                    verification TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )

    def identify_gaps(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        gaps = []
        if not snapshot.get("research"):
            gaps.append({"topic": "autonomous optimization", "gap": "no recent research reports"})
        graph_opportunities = snapshot.get("graph", {}).get("opportunities", [])
        for item in graph_opportunities[:3]:
            gaps.append({"topic": item.get("target", "graph optimization"), "gap": item.get("type", "graph opportunity")})
        weak_skills = snapshot.get("skills", {}).get("recommendations", [])
        for skill in weak_skills[:3]:
            gaps.append({"topic": skill.get("skill", "skill evolution"), "gap": "weak skill score"})
        if not gaps:
            gaps.append({"topic": "ecosystem resilience", "gap": "continuous verification baseline"})
        return gaps

    async def discover(self, snapshot: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
        results = []
        for gap in self.identify_gaps(snapshot)[:limit]:
            research = await self.research.research(gap["topic"], {"gap": gap["gap"]})
            synthesis = self.synthesis.synthesize(gap["topic"], {"gap": gap, "research": research})
            verification = self.verify(research, synthesis)
            record = {
                "id": f"discovery-{uuid.uuid4().hex[:12]}",
                "topic": gap["topic"],
                "gap": gap["gap"],
                "research": research,
                "synthesis": synthesis,
                "verification": verification,
                "created_at": datetime.now().isoformat(),
            }
            with self._lock, sqlite3.connect(self.db_path) as db:
                db.execute(
                    "INSERT INTO discoveries VALUES (?,?,?,?,?,?,?)",
                    (
                        record["id"],
                        record["topic"],
                        record["gap"],
                        json.dumps(research, ensure_ascii=False, default=str),
                        json.dumps(synthesis, ensure_ascii=False, default=str),
                        json.dumps(verification, ensure_ascii=False, default=str),
                        record["created_at"],
                    ),
                )
            results.append(record)
        return results

    def verify(self, research: dict[str, Any], synthesis: dict[str, Any]) -> dict[str, Any]:
        evidence_count = len(research.get("findings", []))
        proposal_count = len(synthesis.get("proposals", []))
        confidence = min(1.0, 0.35 + evidence_count * 0.08 + proposal_count * 0.1)
        return {"verified": confidence >= 0.55, "confidence": round(confidence, 3), "evidence_count": evidence_count}

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,topic,gap,research,synthesis,verification,created_at FROM discoveries ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "topic": row[1],
                "gap": row[2],
                "research": json.loads(row[3] or "{}"),
                "synthesis": json.loads(row[4] or "{}"),
                "verification": json.loads(row[5] or "{}"),
                "created_at": row[6],
            }
            for row in rows
        ]
