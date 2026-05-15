"""Advanced predictive intelligence engine."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "advanced_prediction.db"


class PredictiveIntelligenceEngine:
    """Combines LSTM/RNN predictions with sequence and time-pattern learning."""

    def __init__(self, config: dict | None = None, rnn_engine: Any = None, db_path: str | Path | None = None):
        self.config = config or {}
        configured = self.config.get("prediction", {}).get("db_path")
        self.db_path = Path(db_path or configured or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.rnn = rnn_engine or self._try_load_rnn()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    context TEXT DEFAULT '{}',
                    hour INTEGER,
                    weekday INTEGER,
                    timestamp TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_prediction_actions_time ON actions(timestamp);
                """
            )

    def record_action(self, action: str, context: dict[str, Any] | None = None) -> None:
        now = datetime.now()
        normalized = self._normalize(action)
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "INSERT INTO actions(action,context,hour,weekday,timestamp) VALUES(?,?,?,?,?)",
                (
                    normalized,
                    json.dumps(context or {}, ensure_ascii=False, default=str),
                    now.hour,
                    now.weekday(),
                    now.isoformat(),
                ),
            )
        if self.rnn and hasattr(self.rnn, "record_event"):
            self.rnn.record_event(normalized, json.dumps(context or {}, default=str))

    def predict(self, recent_actions: list[str] | None = None, top_k: int = 5) -> dict[str, Any]:
        candidates: dict[str, dict[str, Any]] = {}
        if self.rnn and hasattr(self.rnn, "predict_next"):
            for item in self.rnn.predict_next(recent_actions, top_k=top_k).get("predictions", []):
                self._merge(candidates, item["command"], item.get("confidence", 0.5), "lstm")
        for item in self._markov_predict(recent_actions, top_k):
            self._merge(candidates, item["action"], item["confidence"], "sequence")
        for item in self._time_predict(top_k):
            self._merge(candidates, item["action"], item["confidence"], "time")

        predictions = sorted(candidates.values(), key=lambda p: p["confidence"], reverse=True)[:top_k]
        return {
            "predictions": predictions,
            "top": predictions[0] if predictions else None,
            "timestamp": datetime.now().isoformat(),
            "method": "lstm+markov+time",
        }

    def suggest_preparation(self, recent_actions: list[str] | None = None) -> list[dict[str, Any]]:
        suggestions = []
        for prediction in self.predict(recent_actions).get("predictions", []):
            action = prediction["action"]
            if prediction["confidence"] < 0.35:
                continue
            if "vscode" in action or "code" in action:
                message = "You usually prepare a coding workspace around now."
                suggested = "prepare_coding_workspace"
            elif "research" in action:
                message = "A research workflow is likely next."
                suggested = "prepare_research_workspace"
            else:
                message = f"Likely next action: {action.replace('_', ' ')}"
                suggested = action
            suggestions.append(
                {
                    "message": message,
                    "action": suggested,
                    "confidence": prediction["confidence"],
                    "sources": prediction["sources"],
                }
            )
        return suggestions[:5]

    def analytics(self) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as db:
            total = db.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
            top = db.execute(
                "SELECT action,COUNT(*) FROM actions GROUP BY action ORDER BY COUNT(*) DESC LIMIT 10"
            ).fetchall()
        return {"total_actions": total, "top_actions": [{"action": r[0], "count": r[1]} for r in top]}

    def _markov_predict(self, recent_actions: list[str] | None, top_k: int) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT action FROM actions ORDER BY id DESC LIMIT 500").fetchall()
        history = [row[0] for row in reversed(rows)]
        if not history:
            return []
        context = [self._normalize(a) for a in (recent_actions or history[-3:])]
        last = context[-1] if context else history[-1]
        next_counts = Counter(history[i + 1] for i in range(len(history) - 1) if history[i] == last)
        if not next_counts:
            next_counts = Counter(history)
        total = sum(next_counts.values()) or 1
        return [
            {"action": action, "confidence": round(count / total, 3)}
            for action, count in next_counts.most_common(top_k)
        ]

    def _time_predict(self, top_k: int) -> list[dict[str, Any]]:
        now = datetime.now()
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute(
                "SELECT action,COUNT(*) FROM actions WHERE hour=? AND weekday=? "
                "GROUP BY action ORDER BY COUNT(*) DESC LIMIT ?",
                (now.hour, now.weekday(), top_k),
            ).fetchall()
        total = sum(row[1] for row in rows) or 1
        return [{"action": row[0], "confidence": round(row[1] / total * 0.8, 3)} for row in rows]

    @staticmethod
    def _merge(candidates: dict[str, dict[str, Any]], action: str, confidence: float, source: str) -> None:
        action = PredictiveIntelligenceEngine._normalize(action)
        if action in candidates:
            candidates[action]["confidence"] = round(min(0.99, candidates[action]["confidence"] + confidence * 0.35), 3)
            candidates[action]["sources"].append(source)
        else:
            candidates[action] = {"action": action, "confidence": round(confidence, 3), "sources": [source]}

    @staticmethod
    def _normalize(action: str) -> str:
        return "_".join(action.lower().strip().split())[:100] or "unknown"

    @staticmethod
    def _try_load_rnn() -> Any:
        try:
            from core.phase2.rnn_engine import BehaviorRNN

            rnn = BehaviorRNN()
            rnn.load_if_exists()
            return rnn
        except Exception:
            return None
