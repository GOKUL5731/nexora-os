"""Sandboxed evolution, mutation scoring, comparisons, and rollback."""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "AI_LAB"
DEFAULT_DB = ROOT / "database" / "evolution.db"
for folder in ["experiments", "evolution", "benchmarks", "deployments", "failed_attempts"]:
    (LAB / folder).mkdir(parents=True, exist_ok=True)


class AdvancedEvolutionEngine:
    """Creates safe variants, scores them, and records deployment history."""

    def __init__(self, config: dict | None = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("evolution", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS mutations (
                    id TEXT PRIMARY KEY,
                    target_type TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    base TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    score REAL DEFAULT 0,
                    metrics TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'created',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS deployments (
                    id TEXT PRIMARY KEY,
                    mutation_id TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    backup_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def mutate_prompt(self, name: str, prompt: str) -> list[dict[str, Any]]:
        variants = [
            prompt.strip() + "\n\nCheck constraints, cite assumptions, and return executable next steps.",
            "Goal: produce a reliable result.\nContext:\n" + prompt.strip() + "\n\nValidate before finalizing.",
            prompt.strip().replace("helpfully", "with precise, tested, context-aware steps"),
        ]
        return [self._record_mutation("prompt", name, prompt, variant) for variant in dict.fromkeys(variants)]

    def mutate_workflow(self, name: str, workflow: dict[str, Any]) -> list[dict[str, Any]]:
        base = json.dumps(workflow, indent=2, sort_keys=True)
        variants = []
        steps = list(workflow.get("steps", []))
        if steps and steps[0].get("action") != "log":
            variants.append({**workflow, "steps": [{"action": "log", "params": {"message": f"Starting {name}"}}] + steps})
        variants.append({**workflow, "steps": [s for s in steps if not (s.get("action") == "wait" and s.get("params", {}).get("seconds", 0) <= 0)]})
        return [self._record_mutation("workflow", name, base, json.dumps(v, indent=2, sort_keys=True)) for v in variants]

    def score_mutation(self, mutation_id: str, scorer: Callable[[str], float] | None = None) -> dict[str, Any]:
        mutation = self.get_mutation(mutation_id)
        variant = mutation["variant"]
        if scorer:
            score = float(scorer(variant))
            metrics = {"external_score": score}
        else:
            base = mutation["base"]
            score = self._intrinsic_score(base, variant)
            metrics = {
                "length_delta": len(variant) - len(base),
                "changed_ratio": round(1.0 - difflib.SequenceMatcher(None, base, variant).ratio(), 3),
            }
        status = "passed" if score >= 0.5 else "failed"
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE mutations SET score=?, metrics=?, status=? WHERE id=?",
                (score, json.dumps(metrics), status, mutation_id),
            )
        if status == "failed":
            (LAB / "failed_attempts" / f"{mutation_id}.json").write_text(json.dumps(mutation, indent=2), encoding="utf-8")
        return {**mutation, "score": score, "metrics": metrics, "status": status}

    def compare_versions(self, base: str, variant: str) -> dict[str, Any]:
        diff = list(difflib.unified_diff(base.splitlines(), variant.splitlines(), lineterm=""))
        ratio = difflib.SequenceMatcher(None, base, variant).ratio()
        return {"similarity": round(ratio, 3), "changed_lines": len(diff), "diff": diff[:200]}

    def deploy_variant(self, mutation_id: str, target_path: str | Path) -> dict[str, Any]:
        mutation = self.get_mutation(mutation_id)
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        backup = LAB / "deployments" / f"{target.name}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
        if target.exists():
            shutil.copy2(target, backup)
        else:
            backup.write_text("", encoding="utf-8")
        target.write_text(mutation["variant"], encoding="utf-8")
        deployment_id = hashlib.sha256(f"{mutation_id}{target}{datetime.now()}".encode()).hexdigest()[:16]
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO deployments VALUES (?,?,?,?,?,?)",
                (deployment_id, mutation_id, str(target), str(backup), "deployed", datetime.now().isoformat()),
            )
        return {"deployment_id": deployment_id, "target_path": str(target), "backup_path": str(backup), "status": "deployed"}

    def rollback(self, deployment_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT target_path,backup_path FROM deployments WHERE id=?",
                (deployment_id,),
            ).fetchone()
        if not row:
            return {"rolled_back": False, "error": f"Deployment not found: {deployment_id}"}
        target, backup = Path(row[0]), Path(row[1])
        if not backup.exists():
            return {"rolled_back": False, "error": f"Backup missing: {backup}"}
        shutil.copy2(backup, target)
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE deployments SET status='rolled_back' WHERE id=?", (deployment_id,))
        return {"rolled_back": True, "target_path": str(target), "backup_path": str(backup)}

    def get_mutation(self, mutation_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as db:
            row = db.execute(
                "SELECT id,target_type,target_name,base,variant,score,metrics,status,created_at "
                "FROM mutations WHERE id=?",
                (mutation_id,),
            ).fetchone()
        if not row:
            raise KeyError(f"Mutation not found: {mutation_id}")
        return {
            "id": row[0],
            "target_type": row[1],
            "target_name": row[2],
            "base": row[3],
            "variant": row[4],
            "score": row[5],
            "metrics": json.loads(row[6] or "{}"),
            "status": row[7],
            "created_at": row[8],
        }

    def _record_mutation(self, target_type: str, target_name: str, base: str, variant: str) -> dict[str, Any]:
        mutation_id = hashlib.sha256(f"{target_type}{target_name}{variant}{datetime.now()}".encode()).hexdigest()[:16]
        record = {
            "id": mutation_id,
            "target_type": target_type,
            "target_name": target_name,
            "base": base,
            "variant": variant,
            "score": 0.0,
            "metrics": {},
            "status": "created",
            "created_at": datetime.now().isoformat(),
        }
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO mutations VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    record["id"],
                    target_type,
                    target_name,
                    base,
                    variant,
                    0.0,
                    "{}",
                    "created",
                    record["created_at"],
                ),
            )
        (LAB / "evolution" / f"{mutation_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record

    @staticmethod
    def _intrinsic_score(base: str, variant: str) -> float:
        if not variant.strip():
            return 0.0
        similarity = difflib.SequenceMatcher(None, base, variant).ratio()
        novelty = 1.0 - similarity
        constraint_bonus = 0.15 if any(word in variant.lower() for word in ["validate", "benchmark", "rollback", "test"]) else 0
        size_penalty = 0.2 if len(variant) > max(4000, len(base) * 3) else 0
        return round(max(0.0, min(1.0, 0.45 + novelty * 0.5 + constraint_bonus - size_penalty)), 3)
