"""Autonomous workflow generation and optimization."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "workflow_generation.db"


class WorkflowGenerator:
    """Learns repeated action patterns and emits executable workflow specs."""

    ACTION_MAP = {
        "research": "llm_query",
        "summarize": "llm_query",
        "code": "llm_query",
        "test": "run_command",
        "open": "open_app",
        "launch": "open_app",
        "wait": "wait",
        "notify": "notify",
        "write": "file_operation",
        "save": "file_operation",
        "http": "http_request",
        "request": "http_request",
    }

    def __init__(self, config: dict | None = None, workflow_engine: Any = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("workflow_generator", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.workflow_engine = workflow_engine
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS action_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    context TEXT DEFAULT '{}',
                    timestamp TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS generated_workflows (
                    name TEXT PRIMARY KEY,
                    spec TEXT NOT NULL,
                    source_pattern TEXT DEFAULT '',
                    score REAL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL DEFAULT 0,
                    metadata TEXT DEFAULT '{}',
                    timestamp TEXT NOT NULL
                );
                """
            )

    def record_action(self, action: str, context: dict[str, Any] | None = None) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO action_events(action,context,timestamp) VALUES(?,?,?)",
                (action[:200], json.dumps(context or {}, default=str), datetime.now().isoformat()),
            )

    def analyze_repetition(self, window: int = 200, min_count: int = 2) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT action,context,timestamp FROM action_events ORDER BY id DESC LIMIT ?",
                (window,),
            ).fetchall()
        actions = [row[0] for row in reversed(rows)]
        pairs = Counter(tuple(actions[i : i + 2]) for i in range(max(0, len(actions) - 1)))
        triples = Counter(tuple(actions[i : i + 3]) for i in range(max(0, len(actions) - 2)))
        patterns = [
            {"sequence": list(seq), "count": count, "length": len(seq)}
            for seq, count in {**pairs, **triples}.items()
            if count >= min_count and len(set(seq)) > 1
        ]
        patterns.sort(key=lambda p: (p["count"], p["length"]), reverse=True)
        return {"total_events": len(actions), "patterns": patterns[:20]}

    def generate_from_goal(self, description: str, name: str | None = None) -> dict[str, Any]:
        workflow_name = name or self._slug(description)
        steps = [{"action": "log", "params": {"message": f"Starting {description}"}}]
        for phrase in self._split_description(description):
            action = self._action_for_phrase(phrase)
            steps.append(self._step_for_action(action, phrase))
        steps.append({"action": "notify", "params": {"message": f"Workflow complete: {workflow_name}"}})
        spec = {
            "name": workflow_name,
            "description": description,
            "steps": self.optimize_steps(steps),
        }
        self.validate_workflow(spec)
        self._save_generated(spec, source_pattern=description, score=0.5 + min(len(spec["steps"]), 10) / 20)
        return spec

    def suggest_from_patterns(self, min_count: int = 2) -> list[dict[str, Any]]:
        suggestions = []
        for pattern in self.analyze_repetition(min_count=min_count)["patterns"]:
            name = self._slug("_".join(pattern["sequence"]))
            steps = [{"action": "log", "params": {"message": f"Running learned pattern {name}"}}]
            for item in pattern["sequence"]:
                steps.append(self._step_for_action(self._action_for_phrase(item), item))
            spec = {
                "name": name,
                "description": f"Learned automation for repeated sequence: {' -> '.join(pattern['sequence'])}",
                "steps": self.optimize_steps(steps),
            }
            self.validate_workflow(spec)
            score = min(1.0, 0.3 + pattern["count"] / 10 + pattern["length"] / 10)
            self._save_generated(spec, " -> ".join(pattern["sequence"]), score)
            suggestions.append({"spec": spec, "pattern": pattern, "score": round(score, 3)})
        return suggestions

    def optimize_steps(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        optimized = []
        for step in steps:
            if optimized and step["action"] == "log" and optimized[-1]["action"] == "log":
                optimized[-1]["params"]["message"] += "; " + step.get("params", {}).get("message", "")
                continue
            if step["action"] == "wait":
                seconds = float(step.get("params", {}).get("seconds", 1))
                if seconds <= 0:
                    continue
                step["params"]["seconds"] = min(seconds, 300)
            optimized.append(step)
        return optimized

    def validate_workflow(self, spec: dict[str, Any]) -> bool:
        if not spec.get("name"):
            raise ValueError("Workflow requires a name")
        if not isinstance(spec.get("steps"), list) or not spec["steps"]:
            raise ValueError("Workflow requires at least one step")
        allowed = {
            "log",
            "notify",
            "run_command",
            "open_app",
            "llm_query",
            "file_operation",
            "http_request",
            "wait",
            "set_variable",
            "condition_branch",
        }
        for idx, step in enumerate(spec["steps"], start=1):
            if step.get("action") not in allowed:
                raise ValueError(f"Step {idx} has unsupported action: {step.get('action')}")
            if "params" not in step:
                step["params"] = {}
        return True

    async def execute_generated(self, spec: dict[str, Any]) -> dict[str, Any]:
        if not self.workflow_engine:
            from core.workflow_engine import WorkflowEngine

            self.workflow_engine = WorkflowEngine()
        started = datetime.now()
        result = await self.workflow_engine.run_spec(spec, save=False)
        duration = (datetime.now() - started).total_seconds() * 1000
        self.record_run(spec["name"], result.get("status", "unknown"), duration, result)
        return result

    def record_run(self, name: str, status: str, duration_ms: float, metadata: dict[str, Any] | None = None) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO workflow_runs(name,status,duration_ms,metadata,timestamp) VALUES(?,?,?,?,?)",
                (
                    name,
                    status,
                    duration_ms,
                    json.dumps(metadata or {}, ensure_ascii=False, default=str),
                    datetime.now().isoformat(),
                ),
            )

    def analytics(self) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as db:
            generated = db.execute("SELECT COUNT(*) FROM generated_workflows").fetchone()[0]
            runs = db.execute("SELECT status,COUNT(*),AVG(duration_ms) FROM workflow_runs GROUP BY status").fetchall()
            top = db.execute(
                "SELECT name,score,source_pattern FROM generated_workflows ORDER BY score DESC LIMIT 10"
            ).fetchall()
        return {
            "generated_workflows": generated,
            "runs_by_status": {
                row[0]: {"count": row[1], "avg_duration_ms": round(row[2] or 0, 2)} for row in runs
            },
            "top_suggestions": [
                {"name": row[0], "score": row[1], "source_pattern": row[2]} for row in top
            ],
        }

    def _save_generated(self, spec: dict[str, Any], source_pattern: str, score: float) -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO generated_workflows VALUES(?,?,?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET
                  spec=excluded.spec,
                  source_pattern=excluded.source_pattern,
                  score=excluded.score,
                  updated_at=excluded.updated_at
                """,
                (
                    spec["name"],
                    json.dumps(spec, ensure_ascii=False, default=str),
                    source_pattern,
                    float(score),
                    now,
                    now,
                ),
            )

    def _step_for_action(self, action: str, phrase: str) -> dict[str, Any]:
        if action == "llm_query":
            return {"action": action, "params": {"prompt": phrase}}
        if action == "run_command":
            command = "python -m pytest" if "test" in phrase.lower() else phrase
            return {"action": action, "params": {"command": command}}
        if action == "open_app":
            return {"action": action, "params": {"app": phrase.replace("open", "").replace("launch", "").strip() or phrase}}
        if action == "file_operation":
            return {"action": action, "params": {"op": "write", "path": "workflow_output.txt", "content": "{{result}}"}}
        if action == "wait":
            return {"action": action, "params": {"seconds": 1}}
        if action == "http_request":
            return {"action": action, "params": {"url": phrase if phrase.startswith("http") else "http://localhost"}}
        return {"action": "log", "params": {"message": phrase}}

    def _action_for_phrase(self, phrase: str) -> str:
        lower = phrase.lower()
        for key, action in self.ACTION_MAP.items():
            if key in lower:
                return action
        return "llm_query"

    @staticmethod
    def _split_description(description: str) -> list[str]:
        parts = [p.strip() for p in re.split(r"\bthen\b|,|;|\n|->", description, flags=re.I) if p.strip()]
        return parts[:12] or [description]

    @staticmethod
    def _slug(text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
        return (slug or "generated_workflow")[:60]
