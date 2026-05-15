"""
JARVIS Phase 2 — Prediction Engine
=====================================
High-level prediction orchestrator that combines:
  - RNN/LSTM behavior predictions
  - Time-of-day heuristics
  - User profile patterns
  - Proactive workflow suggestions

Also handles command classification and latency-optimal routing.

Usage:
    from core.phase2.prediction_engine import PredictionEngine
    engine = PredictionEngine(rnn_engine, behavior_learning)
    prediction = engine.predict("what should I do next?")
    suggestions = engine.get_timed_suggestions()
"""

import logging
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("jarvis.phase2.prediction_engine")

ROOT   = Path(__file__).resolve().parent.parent.parent
DB_DIR = ROOT / "database"


class PredictionEngine:
    """
    Unified prediction interface aggregating RNN + heuristic predictions.
    """

    def __init__(
        self,
        rnn_engine=None,
        behavior_learning=None,
        config: dict = None,
    ):
        self.rnn          = rnn_engine
        self.self_learn   = behavior_learning
        self.config       = config or {}
        self._cache: Dict = {}

    def predict_next_action(self, context: Optional[List[str]] = None) -> Dict:
        """
        Predict the most likely next action(s).
        Combines LSTM output with time and frequency heuristics.
        """
        results = []

        # LSTM prediction
        if self.rnn:
            lstm_pred = self.rnn.predict_next(context, top_k=5)
            for p in lstm_pred.get("predictions", []):
                results.append({
                    "command":    p["command"],
                    "confidence": p["confidence"],
                    "source":     "lstm",
                })

        # Frequency-based from behavior_learning
        if self.self_learn:
            fav = self.self_learn.get_favorite_commands(top_n=5)
            for item in fav:
                # Normalize to 0–1 confidence using success rate
                conf = round(item.get("success_rate", 50) / 100 * 0.6, 3)
                results.append({
                    "command":    item["command"],
                    "confidence": conf,
                    "source":     "frequency",
                })

        # Deduplicate: merge same command from multiple sources
        merged: Dict[str, Dict] = {}
        for r in results:
            cmd = r["command"]
            if cmd in merged:
                merged[cmd]["confidence"] = min(
                    0.99, merged[cmd]["confidence"] + r["confidence"] * 0.3
                )
                merged[cmd]["sources"].append(r["source"])
            else:
                merged[cmd] = {
                    "command":    cmd,
                    "confidence": r["confidence"],
                    "sources":    [r["source"]],
                }

        sorted_results = sorted(merged.values(), key=lambda x: x["confidence"], reverse=True)[:5]

        return {
            "predictions": sorted_results,
            "top":         sorted_results[0] if sorted_results else None,
            "method":      "ensemble",
            "timestamp":   datetime.now().isoformat(),
        }

    def get_timed_suggestions(self) -> List[Dict]:
        """
        Generate time-of-day relevant suggestions.
        """
        now  = datetime.now()
        hour = now.hour
        wday = now.weekday()
        suggestions = []

        # Morning startup
        if 7 <= hour <= 9:
            suggestions.append({
                "message": "Good morning! Shall I open your work apps?",
                "action":  "open_work_apps",
                "category": "morning",
            })
        # Lunch
        elif 12 <= hour <= 13:
            suggestions.append({
                "message": "It's lunchtime. Shall I pause ongoing tasks?",
                "action":  "pause_tasks",
                "category": "lunch",
            })
        # Evening wind-down
        elif 18 <= hour <= 20:
            suggestions.append({
                "message": "End of working day. Want a summary of what was accomplished?",
                "action":  "daily_summary",
                "category": "evening",
            })
        # Late night
        elif hour >= 23 or hour < 5:
            suggestions.append({
                "message": "Working late? I can schedule a reminder to rest.",
                "action":  "set_rest_reminder",
                "category": "late_night",
            })

        # Weekend suggestions
        if wday >= 5:
            suggestions.append({
                "message": "It's the weekend! Model training runs best now with no work interruption.",
                "action":  "suggest_training",
                "category": "weekend",
            })

        # RNN-based
        if self.rnn:
            routine = self.rnn.get_routine_patterns()
            hour_key = f"{hour:02d}:00"
            if hour_key in routine.get("by_hour", {}):
                top_cmd = routine["by_hour"][hour_key][0]["command"]
                suggestions.append({
                    "message": f"At this time you usually: {top_cmd.replace('_', ' ')}",
                    "action":  top_cmd,
                    "category": "routine",
                })

        return suggestions

    def classify_command_type(self, command: str) -> Dict:
        """
        Classify a command into a type category for fast routing.
        Returns type + confidence.
        """
        cmd = command.lower()

        categories = {
            "vision":     ["camera", "detect", "classify", "photo", "see", "look", "screen", "describe"],
            "training":   ["train", "dataset", "collect", "model", "epochs"],
            "prediction": ["predict", "next", "routine", "pattern", "what will"],
            "memory":     ["remember", "recall", "history", "what did i", "notes"],
            "coding":     ["code", "function", "debug", "implement", "python", "script"],
            "system":     ["open", "launch", "close", "volume", "brightness", "shutdown", "restart"],
            "weather":    ["weather", "temperature", "forecast", "rain", "sunny"],
            "general":    [],
        }

        scores: Dict[str, int] = defaultdict(int)
        words = cmd.split()

        for cat, keywords in categories.items():
            for kw in keywords:
                if kw in cmd:
                    scores[cat] += 2
                # Word boundary match
                for w in words:
                    if w.startswith(kw[:3]) and len(kw) > 3:
                        scores[cat] += 1

        if not scores:
            return {"type": "general", "confidence": 0.5}

        best_cat   = max(scores, key=lambda k: scores[k])
        best_score = scores[best_cat]
        total      = sum(scores.values())
        confidence = round(best_score / total, 3) if total > 0 else 0.5

        return {
            "type":       best_cat,
            "confidence": confidence,
            "all_scores": dict(scores),
        }

    def get_command_analytics(self, days: int = 7) -> Dict:
        """
        Return prediction/behavior analytics for the dashboard.
        """
        analytics = {
            "model_ready": False,
            "total_predictions": 0,
            "rnn_stats": {},
            "timed_suggestions": self.get_timed_suggestions(),
        }

        if self.rnn:
            stats = self.rnn.get_stats()
            analytics["rnn_stats"]   = stats
            analytics["model_ready"] = stats.get("model_trained", False)
            analytics["total_predictions"] = stats.get("total_events", 0)

        if self.self_learn:
            report = self.self_learn.get_performance_report(days=days)
            analytics["performance"] = report
            analytics["top_commands"] = self.self_learn.get_favorite_commands(10)

        return analytics
