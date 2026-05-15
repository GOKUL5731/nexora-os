"""Autonomous local research engine for technical planning."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from core.advanced_memory import AdvancedMemorySystem
from core.collaboration_engine import CollaborationEngine


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "research.db"


class AutonomousResearchEngine:
    """Gathers local technical evidence, summarizes it, and stores research memory."""

    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        memory: AdvancedMemorySystem | None = None,
        collaboration: CollaborationEngine | None = None,
        root: str | Path | None = None,
    ):
        self.config = config or {}
        configured = self.config.get("research", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.root = Path(root or ROOT)
        self.memory = memory or AdvancedMemorySystem(self.config)
        self.collaboration = collaboration or CollaborationEngine(self.config)
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS research_reports (
                    id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    findings TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    async def research(self, topic: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        findings = self.gather_local(topic, context or {})
        if not findings:
            agent_result = await self.collaboration.run_task(
                "researcher",
                f"Research implementation options for {topic}",
                context or {},
            )
            findings = [{"source": "researcher_agent", "excerpt": json.dumps(agent_result, default=str)[:1200]}]
        summary = self.summarize(topic, findings)
        plan = self.generate_plan(topic, findings, context or {})
        report_id = f"research-{uuid.uuid4().hex[:12]}"
        report = {
            "id": report_id,
            "topic": topic,
            "findings": findings,
            "summary": summary,
            "implementation_plan": plan,
            "created_at": datetime.now().isoformat(),
        }
        with self._lock, sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO research_reports VALUES (?,?,?,?,?,?)",
                (
                    report_id,
                    topic,
                    json.dumps(findings, ensure_ascii=False, default=str),
                    summary,
                    json.dumps(plan, ensure_ascii=False, default=str),
                    report["created_at"],
                ),
            )
        self.memory.remember_episode("research", summary, {"topic": topic, "report_id": report_id}, importance=0.65)
        self.memory.store_fact("research", topic, {"summary": summary, "report_id": report_id}, confidence=0.75)
        return report

    def gather_local(self, topic: str, context: dict[str, Any] | None = None, limit: int = 12) -> list[dict[str, str]]:
        terms = [term for term in re.split(r"[^a-zA-Z0-9_]+", topic.lower()) if len(term) >= 4]
        if not terms:
            return []
        candidates = []
        for path in self.root.rglob("*"):
            if len(candidates) >= limit:
                break
            if path.is_dir() or path.suffix.lower() not in {".py", ".md", ".txt", ".json"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lowered = text.lower()
            score = sum(lowered.count(term) for term in terms)
            if score:
                excerpt = self._excerpt(text, terms)
                candidates.append({"source": str(path.relative_to(self.root)), "score": str(score), "excerpt": excerpt})
        candidates.sort(key=lambda item: int(item["score"]), reverse=True)
        return candidates[:limit]

    def summarize(self, topic: str, findings: list[dict[str, str]]) -> str:
        if not findings:
            return f"No local evidence found for {topic}; agent research fallback required."
        sources = ", ".join(item["source"] for item in findings[:4])
        return f"Local research for {topic} found {len(findings)} relevant source(s): {sources}."

    def generate_plan(self, topic: str, findings: list[dict[str, str]], context: dict[str, Any]) -> list[dict[str, Any]]:
        evidence = [item["source"] for item in findings[:5]]
        return [
            {"step": "define acceptance criteria", "evidence": evidence, "owner": "planner"},
            {"step": "prototype in sandbox", "evidence": evidence[:2], "owner": "coder"},
            {"step": "run regression and stress tests", "evidence": evidence[:3], "owner": "tester"},
            {"step": "store lessons in memory graph", "evidence": evidence, "owner": "optimizer"},
        ]

    def list_reports(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock, sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT id,topic,findings,summary,plan,created_at FROM research_reports ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "topic": row[1],
                "findings": json.loads(row[2] or "[]"),
                "summary": row[3],
                "implementation_plan": json.loads(row[4] or "[]"),
                "created_at": row[5],
            }
            for row in rows
        ]

    @staticmethod
    def _excerpt(text: str, terms: list[str], size: int = 700) -> str:
        lowered = text.lower()
        index = min((lowered.find(term) for term in terms if term in lowered), default=0)
        start = max(0, index - 120)
        return " ".join(text[start : start + size].split())
