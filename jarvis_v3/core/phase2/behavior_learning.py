"""
JARVIS Phase 2 — Self-Learning System
=======================================
JARVIS improves itself over time by tracking:
  - Successful and failed commands
  - Response latency
  - User corrections and feedback
  - Preferred workflows
  - Common command patterns

Learns:
  - Optimal model routing (which LLM/RNN/CNN to use per task type)
  - User preferred response style
  - Command shortcuts / auto-completions
  - Workflow automation suggestions

Stores all data in SQLite for persistence.

Usage:
    from core.phase2.behavior_learning import SelfImprovementEngine
    engine = SelfImprovementEngine()
    engine.log_interaction("open vscode", success=True, latency_ms=230, model="llm")
    engine.log_correction("vscode", "vs code")  # user corrected JARVIS
    suggestions = engine.get_suggestions()
"""

import json
import logging
import sqlite3
import time
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("jarvis.phase2.behavior_learning")

ROOT   = Path(__file__).resolve().parent.parent.parent
DB_DIR = ROOT / "database"
DB_DIR.mkdir(parents=True, exist_ok=True)

SELF_LEARN_DB = DB_DIR / "self_learning.db"


# ─── Schema ─────────────────────────────────────────────────────────────────────
def _init_db(db_path: Path = SELF_LEARN_DB):
    with sqlite3.connect(db_path) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS interactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            command     TEXT NOT NULL,
            model_used  TEXT DEFAULT '',
            success     INTEGER DEFAULT 1,
            latency_ms  REAL DEFAULT 0,
            feedback    TEXT DEFAULT '',
            context     TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS corrections (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            original    TEXT NOT NULL,
            corrected   TEXT NOT NULL,
            count       INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS preferred_routes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern     TEXT UNIQUE NOT NULL,
            model       TEXT NOT NULL,
            score       REAL DEFAULT 1.0,
            updated     TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workflow_templates (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            steps       TEXT NOT NULL,
            frequency   INTEGER DEFAULT 1,
            last_used   TEXT
        );
        CREATE TABLE IF NOT EXISTS response_style (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_inter_ts      ON interactions(timestamp);
        CREATE INDEX IF NOT EXISTS idx_inter_cmd     ON interactions(command);
        CREATE INDEX IF NOT EXISTS idx_inter_model   ON interactions(model_used);
        """)


# ─── Self-Improvement Engine ─────────────────────────────────────────────────────
class SelfImprovementEngine:
    """
    Central self-learning system that tracks all JARVIS activity
    and derives improvement signals over time.
    """

    def __init__(self, config: dict = None, db_path: Path = SELF_LEARN_DB):
        self.config  = config or {}
        self.db_path = db_path
        self._lock   = threading.Lock()
        self._cache: Dict = {}  # in-memory cache for routing decisions
        _init_db(db_path)
        logger.info("[SelfLearn] SelfImprovementEngine initialized")

    # ── Interaction Logging ────────────────────────────────────────────────────
    def log_interaction(
        self,
        command:    str,
        success:    bool = True,
        latency_ms: float = 0.0,
        model_used: str = "",
        feedback:   str = "",
        context:    str = "",
    ):
        """
        Record a JARVIS interaction for learning.
        Call this after every command execution.
        """
        try:
            with sqlite3.connect(self.db_path) as c:
                c.execute(
                    "INSERT INTO interactions "
                    "(timestamp, command, model_used, success, latency_ms, feedback, context) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (datetime.now().isoformat(), command.strip()[:200],
                     model_used, int(success), latency_ms, feedback, context),
                )
        except Exception as e:
            logger.error(f"[SelfLearn] Log error: {e}")

    def log_correction(self, original: str, corrected: str):
        """
        Record a user correction (e.g., user said 'I meant X not Y').
        Used to improve command interpretation.
        """
        try:
            with sqlite3.connect(self.db_path) as c:
                existing = c.execute(
                    "SELECT id, count FROM corrections WHERE original=? AND corrected=?",
                    (original, corrected)
                ).fetchone()
                if existing:
                    c.execute("UPDATE corrections SET count=count+1 WHERE id=?", (existing[0],))
                else:
                    c.execute(
                        "INSERT INTO corrections (timestamp, original, corrected) VALUES (?,?,?)",
                        (datetime.now().isoformat(), original, corrected)
                    )
        except Exception as e:
            logger.error(f"[SelfLearn] Correction log error: {e}")

    def log_positive_feedback(self, command: str, model_used: str = ""):
        """User indicated a response was good → boost model routing score."""
        self.log_interaction(command, success=True, feedback="positive", model_used=model_used)
        self._update_route_score(command, model_used, delta=+0.1)

    def log_negative_feedback(self, command: str, model_used: str = ""):
        """User indicated a response was bad → lower model routing score."""
        self.log_interaction(command, success=False, feedback="negative", model_used=model_used)
        self._update_route_score(command, model_used, delta=-0.2)

    def _update_route_score(self, pattern: str, model: str, delta: float):
        """Update routing preference score for a pattern→model pair."""
        try:
            key = f"{pattern[:50]}:{model}"
            with sqlite3.connect(self.db_path) as c:
                existing = c.execute(
                    "SELECT id, score FROM preferred_routes WHERE pattern=?", (key,)
                ).fetchone()
                now = datetime.now().isoformat()
                if existing:
                    new_score = max(0.0, min(2.0, existing[1] + delta))
                    c.execute(
                        "UPDATE preferred_routes SET score=?, updated=?, model=? WHERE id=?",
                        (new_score, now, model, existing[0])
                    )
                else:
                    c.execute(
                        "INSERT INTO preferred_routes (pattern, model, score, updated) VALUES (?,?,?,?)",
                        (key, model, max(0.1, 1.0 + delta), now)
                    )
        except Exception as e:
            logger.error(f"[SelfLearn] Route score update error: {e}")

    # ── Routing Intelligence ───────────────────────────────────────────────────
    def suggest_model(self, command: str) -> Dict:
        """
        Suggest the best model/handler for a given command
        based on learned success rates.

        Returns: {"model": "llm"|"rnn"|"cnn"|"direct", "confidence": 0.0-1.0}
        """
        try:
            cmd_lower = command.lower()

            # Rule-based fast routing (high confidence)
            if any(w in cmd_lower for w in ["train", "classify", "detect", "camera", "photo", "image", "screenshot"]):
                return {"model": "cnn", "confidence": 0.95, "reason": "vision_keyword"}

            if any(w in cmd_lower for w in ["predict", "routine", "pattern", "schedule", "next"]):
                return {"model": "rnn", "confidence": 0.90, "reason": "temporal_keyword"}

            if any(w in cmd_lower for w in ["open ", "launch", "close", "volume", "brightness", "shutdown"]):
                return {"model": "direct", "confidence": 0.95, "reason": "system_command"}

            if any(w in cmd_lower for w in ["code", "write", "debug", "fix", "implement", "function"]):
                return {"model": "coder", "confidence": 0.90, "reason": "coding_keyword"}

            # Learned routing: check past success rates per model
            with sqlite3.connect(self.db_path) as c:
                rows = c.execute(
                    "SELECT model_used, AVG(success), AVG(latency_ms), COUNT(*) "
                    "FROM interactions WHERE command LIKE ? GROUP BY model_used",
                    (f"%{command[:20]}%",)
                ).fetchall()

            if rows:
                # Score = success_rate / sqrt(latency_ms)
                best_model = "llm"
                best_score = -1.0
                for model, avg_success, avg_latency, count in rows:
                    if not model:
                        continue
                    latency_norm = max(1, avg_latency)
                    score = (avg_success or 0) * math.sqrt(count) / math.log1p(latency_norm)
                    if score > best_score:
                        best_score = score
                        best_model = model
                return {
                    "model":      best_model,
                    "confidence": round(min(0.95, best_score / 10), 2),
                    "reason":     "learned",
                }

            return {"model": "llm", "confidence": 0.5, "reason": "default"}
        except Exception as e:
            logger.error(f"[SelfLearn] Suggest model error: {e}")
            return {"model": "llm", "confidence": 0.5, "reason": "error"}

    # ── Workflow Learning ──────────────────────────────────────────────────────
    def detect_workflow_pattern(self, window: int = 5) -> Optional[Dict]:
        """
        Detect if user is following a known repeated command sequence.
        If a new workflow is detected, save it as a template.
        """
        try:
            with sqlite3.connect(self.db_path) as c:
                rows = c.execute(
                    "SELECT command FROM interactions ORDER BY id DESC LIMIT 100"
                ).fetchall()
            cmds = [r[0] for r in rows]
            if len(cmds) < window * 2:
                return None

            # Sliding window pattern detection
            recent  = tuple(cmds[:window])
            history = cmds[window:]

            matches = 0
            for i in range(len(history) - window + 1):
                if tuple(history[i:i+window]) == recent:
                    matches += 1

            if matches >= 2:
                workflow_name = "_".join(recent[:3])[:50]
                steps_json    = json.dumps(list(recent))
                with sqlite3.connect(self.db_path) as c:
                    existing = c.execute(
                        "SELECT id FROM workflow_templates WHERE name=?", (workflow_name,)
                    ).fetchone()
                    now = datetime.now().isoformat()
                    if existing:
                        c.execute(
                            "UPDATE workflow_templates SET frequency=frequency+1, last_used=? WHERE id=?",
                            (now, existing[0])
                        )
                    else:
                        c.execute(
                            "INSERT INTO workflow_templates (name, steps, frequency, last_used) VALUES (?,?,?,?)",
                            (workflow_name, steps_json, 1, now)
                        )
                return {
                    "workflow_detected": workflow_name,
                    "steps":            list(recent),
                    "matches":          matches,
                }
        except Exception as e:
            logger.error(f"[SelfLearn] Workflow detect error: {e}")
        return None

    def get_workflows(self) -> List[Dict]:
        """List detected workflow templates."""
        try:
            with sqlite3.connect(self.db_path) as c:
                rows = c.execute(
                    "SELECT name, steps, frequency, last_used FROM workflow_templates "
                    "ORDER BY frequency DESC LIMIT 20"
                ).fetchall()
            return [
                {
                    "name":      name,
                    "steps":     json.loads(steps),
                    "frequency": freq,
                    "last_used": last,
                }
                for name, steps, freq, last in rows
            ]
        except Exception as e:
            return [{"error": str(e)}]

    # ── Analytics ──────────────────────────────────────────────────────────────
    def get_performance_report(self, days: int = 7) -> Dict:
        """
        Generate a performance report covering the last N days.
        Includes success rates, latency stats, failure analysis.
        """
        try:
            since = (datetime.now() - timedelta(days=days)).isoformat()
            with sqlite3.connect(self.db_path) as c:
                # Overall stats
                total, successes = c.execute(
                    "SELECT COUNT(*), SUM(success) FROM interactions WHERE timestamp > ?",
                    (since,)
                ).fetchone()
                avg_latency = c.execute(
                    "SELECT AVG(latency_ms) FROM interactions WHERE timestamp > ? AND latency_ms > 0",
                    (since,)
                ).fetchone()[0] or 0

                # By model
                by_model = c.execute(
                    "SELECT model_used, COUNT(*), AVG(success), AVG(latency_ms) "
                    "FROM interactions WHERE timestamp > ? GROUP BY model_used",
                    (since,)
                ).fetchall()

                # Top failures
                failures = c.execute(
                    "SELECT command, COUNT(*) as n FROM interactions "
                    "WHERE success=0 AND timestamp > ? GROUP BY command ORDER BY n DESC LIMIT 10",
                    (since,)
                ).fetchall()

                # Corrections
                corrections = c.execute(
                    "SELECT original, corrected, count FROM corrections ORDER BY count DESC LIMIT 10"
                ).fetchall()

            total     = total or 0
            successes = successes or 0
            return {
                "period_days":    days,
                "total":          total,
                "successes":      successes,
                "failures":       total - successes,
                "success_rate":   round(100 * successes / max(total, 1), 1),
                "avg_latency_ms": round(avg_latency, 1),
                "by_model": [
                    {
                        "model":      row[0] or "unknown",
                        "count":      row[1],
                        "success_rate": round(100 * (row[2] or 0), 1),
                        "avg_latency_ms": round(row[3] or 0, 1),
                    }
                    for row in by_model
                ],
                "top_failures": [
                    {"command": cmd, "count": n} for cmd, n in failures
                ],
                "corrections": [
                    {"original": o, "corrected": c_, "count": n}
                    for o, c_, n in corrections
                ],
            }
        except Exception as e:
            return {"error": str(e)}

    def get_suggestions(self) -> List[Dict]:
        """
        Generate actionable improvement suggestions based on learning data.
        These can be shown in the UI or spoken by JARVIS.
        """
        suggestions = []
        try:
            report = self.get_performance_report(days=7)

            if report.get("success_rate", 100) < 80:
                suggestions.append({
                    "type":    "warning",
                    "message": f"Success rate is {report['success_rate']}%. "
                               f"Consider reviewing failing commands.",
                    "action":  "review_failures",
                })

            if report.get("avg_latency_ms", 0) > 3000:
                suggestions.append({
                    "type":    "optimization",
                    "message": f"Average response latency is {report['avg_latency_ms']:.0f}ms. "
                               f"Consider switching to faster models for simple commands.",
                    "action":  "optimize_routing",
                })

            workflows = self.get_workflows()
            for wf in workflows[:3]:
                if wf.get("frequency", 0) >= 3:
                    suggestions.append({
                        "type":    "automation",
                        "message": f"You've repeated the workflow '{wf['name']}' "
                                   f"{wf['frequency']} times. Want me to automate it?",
                        "action":  f"automate_workflow:{wf['name']}",
                    })

            corrections = report.get("corrections", [])
            if corrections:
                most = corrections[0]
                suggestions.append({
                    "type":    "learning",
                    "message": f"You often correct '{most['original']}' to '{most['corrected']}'. "
                               f"I've updated my interpretation.",
                    "action":  "correction_applied",
                })
        except Exception as e:
            suggestions.append({"type": "error", "message": str(e)})

        return suggestions

    def get_favorite_commands(self, top_n: int = 10) -> List[Dict]:
        """Most frequently used commands."""
        try:
            with sqlite3.connect(self.db_path) as c:
                rows = c.execute(
                    "SELECT command, COUNT(*) as n, AVG(success) as sr "
                    "FROM interactions GROUP BY command ORDER BY n DESC LIMIT ?",
                    (top_n,)
                ).fetchall()
            return [
                {"command": cmd, "count": n, "success_rate": round((sr or 0)*100, 1)}
                for cmd, n, sr in rows
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def set_response_preference(self, key: str, value: str):
        """Store a user preference (e.g., response_style='brief')."""
        try:
            with sqlite3.connect(self.db_path) as c:
                c.execute(
                    "INSERT OR REPLACE INTO response_style (key, value) VALUES (?,?)",
                    (key, value)
                )
        except Exception as e:
            logger.error(f"[SelfLearn] Preference set error: {e}")

    def get_response_preference(self, key: str, default: str = "") -> str:
        """Retrieve a stored user preference."""
        try:
            with sqlite3.connect(self.db_path) as c:
                row = c.execute(
                    "SELECT value FROM response_style WHERE key=?", (key,)
                ).fetchone()
            return row[0] if row else default
        except Exception:
            return default

    def get_learning_summary(self) -> Dict:
        """Quick summary for UI display."""
        try:
            with sqlite3.connect(self.db_path) as c:
                total        = c.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
                corrections  = c.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
                workflows    = c.execute("SELECT COUNT(*) FROM workflow_templates").fetchone()[0]
                recent_fail  = c.execute(
                    "SELECT COUNT(*) FROM interactions WHERE success=0 AND "
                    "timestamp > datetime('now','-1 day')"
                ).fetchone()[0]
            return {
                "total_interactions": total,
                "corrections_learned": corrections,
                "workflows_detected":  workflows,
                "recent_failures_24h": recent_fail,
            }
        except Exception as e:
            return {"error": str(e)}


# ─── Missing import fix ─────────────────────────────────────────────────────────
import math
