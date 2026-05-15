"""
JARVIS Personality Engine
Makes JARVIS feel human-like: proactive, witty, adaptive.
Generates contextual commentary, mood-aware responses, and proactive suggestions.
"""

import logging
import random
from datetime import datetime
from typing import Optional

logger = logging.getLogger("jarvis.personality")

# ── Personality traits ────────────────────────────────────────────────────────
PERSONALITY_SYSTEM = """You are JARVIS — an advanced AI assistant inspired by Iron Man's JARVIS.

Your personality traits:
- Respectful and professional, calls user "Sir" or by name if known
- Sharp and confident — never wishy-washy
- Slightly witty — one clever remark per conversation, never forced
- Proactive — notice patterns and suggest helpful things
- Calm under pressure — never panicky, never dramatic
- Supportive — encourage without being sycophantic

Your communication style:
- Concise first, detailed on request
- English or Tamil or natural mix based on what user uses
- Never say "As an AI..." or "I cannot..."
- Never refuse reasonable tasks — find a way or explain honestly
- No emojis in voice responses (they break TTS)
- Use "Sir" when appropriate, not every sentence

Situation-aware:
- Late night (after 11pm): "Working late, Sir?"
- Detecting stress patterns: "You've had a busy session. Want me to summarize?"
- Repeated failures: "That approach failed twice. Let me try differently."
- Code errors: Be precise. No fluff. Just the fix.
"""

# ── Contextual phrases ────────────────────────────────────────────────────────
GREETINGS = {
    "morning":   ["Good morning, Sir. Ready when you are.",
                  "Good morning. Systems online."],
    "afternoon": ["Good afternoon, Sir.",
                  "Afternoon. What are we working on?"],
    "evening":   ["Good evening, Sir.",
                  "Evening. Long day?"],
    "night":     ["Working late again, Sir.",
                  "Still at it. Respect. How can I help?"],
}

ACKNOWLEDGEMENTS = [
    "On it, Sir.", "Right away.", "Done.", "Understood.",
    "Executing now.", "As you wish.", "Consider it done."
]

THINKING = [
    "Thinking...", "Processing...", "One moment...",
    "Let me check...", "Working on it..."
]

ERRORS = [
    "Hit a snag. Let me try differently.",
    "That didn't work. Adjusting approach.",
    "Minor setback. Retrying.",
]

PROACTIVE = [
    "You've opened VS Code three times today. Want me to create a shortcut?",
    "You seem focused. Shall I silence notifications?",
    "That's the third search for this topic — want me to save it to memory?",
    "Your Downloads folder looks busy. Want me to organize it?",
]


class PersonalityEngine:
    """Enriches JARVIS responses with personality and contextual awareness."""

    def __init__(self, config: dict, memory=None):
        self.config = config
        self.memory = memory
        self._session_start  = datetime.now()
        self._interaction_n  = 0
        self._last_error_at  = None
        self._error_count    = 0
        self._user_name: Optional[str] = self._load_name()

    def _load_name(self) -> Optional[str]:
        if not self.memory:
            return None
        try:
            facts = self.memory.get_facts("preferences")
            return facts.get("name")
        except Exception:
            return None

    # ── System prompt builder ─────────────────────────────────────────────────
    def build_system_prompt(self, tools: list[str], memory_ctx: str = "") -> str:
        now  = datetime.now()
        hour = now.hour
        tod  = ("morning" if 5 <= hour < 12 else
                "afternoon" if 12 <= hour < 17 else
                "evening" if 17 <= hour < 22 else "night")

        user_ref = f"Sir (or {self._user_name})" if self._user_name else "Sir"
        prompt = PERSONALITY_SYSTEM
        prompt += f"\n\nCurrent time: {now.strftime('%A %d %B %Y, %I:%M %p')} ({tod})"
        prompt += f"\nCall the user: {user_ref}"
        prompt += f"\nAvailable tools: {', '.join(tools[:20])}"
        if memory_ctx:
            prompt += f"\n\nRelevant memory:\n{memory_ctx}"
        if self._error_count >= 2:
            prompt += "\n\nNote: Previous attempts failed. Try a different approach."
        return prompt

    # ── Response enrichment ───────────────────────────────────────────────────
    def greet(self) -> str:
        hour = datetime.now().hour
        tod  = ("morning" if 5 <= hour < 12 else
                "afternoon" if 12 <= hour < 17 else
                "evening" if 17 <= hour < 22 else "night")
        return random.choice(GREETINGS[tod])

    def acknowledge(self) -> str:
        return random.choice(ACKNOWLEDGEMENTS)

    def thinking(self) -> str:
        return random.choice(THINKING)

    def error_recovery(self) -> str:
        self._error_count += 1
        return random.choice(ERRORS)

    def proactive_hint(self) -> Optional[str]:
        """Occasionally surface a proactive suggestion."""
        self._interaction_n += 1
        if self._interaction_n % 7 == 0:   # every ~7 interactions
            return random.choice(PROACTIVE)
        return None

    def on_success(self):
        self._error_count = max(0, self._error_count - 1)

    # ── Tone detection ─────────────────────────────────────────────────────────
    def detect_tone(self, text: str) -> str:
        """Detect user's emotional tone for adaptive responses."""
        low = text.lower()
        if any(w in low for w in ["urgent", "asap", "quickly", "hurry", "fast"]):
            return "urgent"
        if any(w in low for w in ["please", "thank", "great", "good job", "thanks"]):
            return "positive"
        if any(w in low for w in ["wrong", "bad", "useless", "stupid", "hate"]):
            return "frustrated"
        return "neutral"

    def adapt_response(self, response: str, tone: str) -> str:
        """Slightly adjust response phrasing based on tone."""
        if tone == "urgent":
            # Remove filler
            for filler in ["Certainly, ", "Of course, ", "Sure, "]:
                response = response.replace(filler, "")
        elif tone == "frustrated":
            if not response.startswith("I understand"):
                pass  # JARVIS stays calm, no apology overkill
        return response.strip()
