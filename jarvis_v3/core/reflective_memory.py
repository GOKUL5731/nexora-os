"""Reflective memory for lessons learned from successes and failures."""

from __future__ import annotations

from typing import Any

from core.advanced_memory import AdvancedMemorySystem


class ReflectiveMemory:
    """Stores durable lessons that should influence future planning."""

    def __init__(self, config: dict | None = None, memory: AdvancedMemorySystem | None = None):
        self.config = config or {}
        self.memory = memory or AdvancedMemorySystem(self.config)

    def remember_lesson(
        self,
        title: str,
        lesson: str,
        outcome: str,
        context: dict[str, Any] | None = None,
        confidence: float = 0.7,
    ) -> str:
        payload = {"title": title, "lesson": lesson, "outcome": outcome, "context": context or {}}
        self.memory.remember_episode("reflective_lesson", lesson, payload, importance=confidence)
        return self.memory.store_fact("reflective_memory", title, payload, confidence=confidence)

    def lessons(self) -> dict[str, Any]:
        return self.memory.list_facts("reflective_memory")

    def lessons_for_context(self, text: str) -> list[dict[str, Any]]:
        terms = {w.lower() for w in text.split() if len(w) > 3}
        matches = []
        for title, lesson in self.lessons().items():
            haystack = f"{title} {lesson.get('lesson', '')} {lesson.get('outcome', '')}".lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                matches.append({"title": title, "lesson": lesson, "score": score})
        return sorted(matches, key=lambda item: item["score"], reverse=True)
