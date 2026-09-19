from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from ..core.event_bus import EventBus


class LearningManager:
    """Durable learning job runner layered over knowledge and memory.

    A learning job indexes source-attributed domain knowledge, tests whether
    that knowledge can be recalled, and stores an episodic outcome. It does not
    retrain a model or grant itself new permissions.
    """

    def __init__(self, database: Path, bus: EventBus, knowledge: Any, memory: Any) -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        self.database = database
        self.bus = bus
        self.knowledge = knowledge
        self.memory = memory
        self._db = sqlite3.connect(database, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS learning_jobs(
            id INTEGER PRIMARY KEY, domain TEXT NOT NULL, goal TEXT NOT NULL,
            status TEXT NOT NULL, resources TEXT NOT NULL, expected_terms TEXT NOT NULL,
            result TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL,
            updated_at REAL NOT NULL, completed_at REAL)"""
        )
        self._db.commit()

    def start_job(
        self,
        domain: str,
        goal: str = "",
        resources: list[dict[str, Any]] | None = None,
        expected_terms: list[str] | None = None,
    ) -> dict[str, Any]:
        normalized = " ".join(domain.lower().split())
        if not normalized:
            return {"ok": False, "error": "domain_required"}
        now = time.time()
        cur = self._db.execute(
            """INSERT INTO learning_jobs(domain, goal, status, resources, expected_terms, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?)""",
            (
                normalized,
                goal or f"Learn and verify {normalized}",
                "PENDING",
                json.dumps(resources or []),
                json.dumps(expected_terms or []),
                now,
                now,
            ),
        )
        self._db.commit()
        job_id = int(cur.lastrowid)
        self.bus.publish("learning.job.created", {"job_id": job_id, "domain": normalized}, "learning_manager")
        return self.run_job(job_id)

    def run_job(self, job_id: int) -> dict[str, Any]:
        job = self.get_job(job_id)
        if job is None:
            return {"ok": False, "error": "job_not_found"}
        if job["status"] in {"PASSED", "FAILED"}:
            return {"ok": True, "job": job}

        self._set_status(job_id, "RUNNING")
        self.bus.publish("learning.job.started", {"job_id": job_id, "domain": job["domain"]}, "learning_manager")
        try:
            resources = job["resources"]
            learned = self.knowledge.learn_domain(job["domain"], resources or None)
            tests = self._self_test(job["domain"], job["expected_terms"])
            passed = bool(learned.get("ok")) and tests["passed"]
            status = "PASSED" if passed else "FAILED"
            result = {
                "learned": learned,
                "self_test": tests,
                "message": "learning job passed" if passed else "learning job failed self-test",
            }
            self._complete(job_id, status, result)
            self.memory.record_episode(
                job["goal"],
                f"learn_domain:{job['domain']}",
                result["message"],
                outcome="success" if passed else "failed",
                evidence=[
                    {"source": "knowledge.learn_domain", "ok": learned.get("ok"), "domain": job["domain"]},
                    {"source": "learning.self_test", "passed": tests["passed"], "checks": tests["checks"]},
                ],
                confidence=0.85 if passed else 0.35,
                importance=0.75,
                tags=["learning", job["domain"]],
            )
            final_job = self.get_job(job_id) or {}
            self.bus.publish("learning.job.completed", final_job, "learning_manager")
            return {"ok": passed, "job": final_job}
        except Exception as exc:
            result = {"error": str(exc)}
            self._complete(job_id, "FAILED", result)
            self.bus.publish("learning.job.failed", {"job_id": job_id, "error": str(exc)}, "learning_manager")
            return {"ok": False, "job": self.get_job(job_id), "error": str(exc)}

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        row = self._db.execute("SELECT * FROM learning_jobs WHERE id=?", (job_id,)).fetchone()
        return self._job(row) if row else None

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM learning_jobs ORDER BY updated_at DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
        return [self._job(row) for row in rows]

    def status(self) -> dict[str, Any]:
        rows = self._db.execute("SELECT status, COUNT(*) count FROM learning_jobs GROUP BY status").fetchall()
        return {"database": str(self.database), "jobs": {row["status"]: row["count"] for row in rows}}

    def _self_test(self, domain: str, expected_terms: list[str]) -> dict[str, Any]:
        terms = [term.strip().lower() for term in expected_terms if term.strip()]
        query = " ".join(terms) if terms else domain
        hits = self.knowledge.search(query, domain, limit=5)
        haystack = " ".join(
            f"{hit.get('title', '')} {hit.get('content', '')} {' '.join(hit.get('tags', []))}".lower()
            for hit in hits
        )
        checks = [
            {"term": term, "passed": term in haystack}
            for term in terms
        ]
        passed = bool(hits) and all(check["passed"] for check in checks)
        return {"passed": passed, "query": query, "hit_count": len(hits), "checks": checks}

    def _set_status(self, job_id: int, status: str) -> None:
        self._db.execute(
            "UPDATE learning_jobs SET status=?, updated_at=? WHERE id=?",
            (status, time.time(), job_id),
        )
        self._db.commit()

    def _complete(self, job_id: int, status: str, result: dict[str, Any]) -> None:
        now = time.time()
        self._db.execute(
            "UPDATE learning_jobs SET status=?, result=?, updated_at=?, completed_at=? WHERE id=?",
            (status, json.dumps(result), now, now, job_id),
        )
        self._db.commit()

    @staticmethod
    def _job(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "domain": row["domain"],
            "goal": row["goal"],
            "status": row["status"],
            "resources": json.loads(row["resources"]),
            "expected_terms": json.loads(row["expected_terms"]),
            "result": json.loads(row["result"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "completed_at": row["completed_at"],
        }
