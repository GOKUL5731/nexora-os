"""
JARVIS Behavior Trainer — learns user habits and optimizes performance.
Runs as a background loop. Writes insights to memory and config.
"""

import asyncio
import json
import logging
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("jarvis.trainer")


class BehaviorTrainer:
    """
    Learns from interaction history to:
    - Identify frequently used commands → cache them
    - Detect peak usage hours → pre-warm models
    - Find favorite apps → build quick-open list
    - Spot repeated failures → generate fix strategies
    - Suggest automations based on behavior patterns
    """

    def __init__(self, config: dict, memory, llm_router=None):
        self.config  = config
        self.memory  = memory
        self.router  = llm_router
        self.interval = config.get("learning", {}).get("interval_minutes", 30) * 60
        self._running = False
        self._cache: dict[str, str] = {}   # prompt_hash → response
        self._insights: list[dict] = []
        self._train_db = Path(memory.db_path).parent / "trainer.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._train_db) as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS command_freq (
                    pattern TEXT PRIMARY KEY,
                    count   INTEGER DEFAULT 1,
                    last_seen TEXT
                );
                CREATE TABLE IF NOT EXISTS app_usage (
                    app  TEXT PRIMARY KEY,
                    opens INTEGER DEFAULT 1,
                    last_open TEXT
                );
                CREATE TABLE IF NOT EXISTS insights (
                    id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts    TEXT,
                    type  TEXT,
                    data  TEXT
                );
                CREATE TABLE IF NOT EXISTS cached_responses (
                    key      TEXT PRIMARY KEY,
                    response TEXT,
                    hits     INTEGER DEFAULT 0,
                    ts       TEXT
                );
            """)

    # ── Background loop ───────────────────────────────────────────────────────
    async def start(self):
        self._running = True
        logger.info(f"Behavior trainer started (cycle every {self.interval//60}min)")
        # First analysis after 60s
        await asyncio.sleep(60)
        while self._running:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error(f"Trainer cycle error: {e}")
            await asyncio.sleep(self.interval)

    def stop(self):
        self._running = False

    async def _run_cycle(self):
        interactions = self._load_recent(hours=self.interval / 3600)
        if len(interactions) < 3:
            return
        logger.info(f"Trainer analyzing {len(interactions)} interactions...")
        self._analyze_command_frequency(interactions)
        self._analyze_app_usage(interactions)
        await self._generate_insights(interactions)
        self._build_response_cache(interactions)
        logger.info("Trainer cycle complete")

    # ── Analysis methods ──────────────────────────────────────────────────────
    def _load_recent(self, hours: float) -> list[dict]:
        since = (datetime.now() - timedelta(hours=max(1, hours))).isoformat()
        try:
            with sqlite3.connect(self.memory.db_path) as c:
                rows = c.execute(
                    "SELECT user_input, jarvis_resp, outcome, timestamp "
                    "FROM interactions WHERE timestamp>? ORDER BY timestamp DESC",
                    (since,)
                ).fetchall()
            return [{"input": r[0], "response": r[1], "outcome": r[2], "ts": r[3]}
                    for r in rows]
        except Exception:
            return []

    def _analyze_command_frequency(self, interactions: list):
        """Count command patterns and store top ones."""
        import re
        patterns = []
        for item in interactions:
            # Normalize: lowercase, strip specific nouns
            text = item["input"].lower().strip()
            text = re.sub(r"\b(the|a|an|my|your|please|can you|could you)\b", "", text)
            text = text.strip()[:60]
            patterns.append(text)

        counter = Counter(patterns)
        with sqlite3.connect(self._train_db) as c:
            for pat, count in counter.most_common(20):
                c.execute("""
                    INSERT INTO command_freq(pattern, count, last_seen) VALUES(?,?,?)
                    ON CONFLICT(pattern) DO UPDATE SET count=count+?, last_seen=?
                """, (pat, count, datetime.now().isoformat(), count, datetime.now().isoformat()))

    def _analyze_app_usage(self, interactions: list):
        """Track which apps are opened most often."""
        import re
        app_pattern = re.compile(r"\b(?:open|launch|start)\s+([a-zA-Z0-9\s]+?)(?:\s|$)", re.I)
        with sqlite3.connect(self._train_db) as c:
            for item in interactions:
                m = app_pattern.search(item["input"])
                if m:
                    app = m.group(1).strip()[:40]
                    c.execute("""
                        INSERT INTO app_usage(app, opens, last_open) VALUES(?,1,?)
                        ON CONFLICT(app) DO UPDATE SET opens=opens+1, last_open=?
                    """, (app, datetime.now().isoformat(), datetime.now().isoformat()))

    def _build_response_cache(self, interactions: list):
        """Cache responses to frequent successful queries."""
        import hashlib
        successes = [i for i in interactions if i["outcome"] == "success"]
        freq_map: dict[str, int] = {}
        for item in successes:
            key = hashlib.md5(item["input"].lower().strip().encode()).hexdigest()[:12]
            freq_map[key] = freq_map.get(key, 0) + 1

        with sqlite3.connect(self._train_db) as c:
            for item in successes:
                key = hashlib.md5(item["input"].lower().strip().encode()).hexdigest()[:12]
                if freq_map[key] >= 2:   # cache if seen 2+ times
                    c.execute("""
                        INSERT INTO cached_responses(key, response, hits, ts) VALUES(?,?,?,?)
                        ON CONFLICT(key) DO UPDATE SET hits=hits+1
                    """, (key, item["response"][:500], 1, datetime.now().isoformat()))

    async def _generate_insights(self, interactions: list):
        """Use LLM to identify behavioral patterns."""
        if not self.router:
            return
        sample = "\n".join(f"- {i['input'][:60]}" for i in interactions[:10])
        try:
            raw = await self.router.complete_async(
                f"Analyze these JARVIS user commands and identify 2-3 behavioral patterns "
                f"or automation opportunities:\n{sample}\n\n"
                f"Return JSON: [{{\"pattern\":\"...\",\"suggestion\":\"...\"}}]\n"
                f"Return ONLY JSON.",
                temperature=0.2,
            )
            raw = raw.strip().replace("```json","").replace("```","").strip()
            s, e = raw.find("["), raw.rfind("]") + 1
            if s >= 0:
                patterns = json.loads(raw[s:e])
                with sqlite3.connect(self._train_db) as c:
                    for p in patterns:
                        c.execute(
                            "INSERT INTO insights(ts,type,data) VALUES(?,?,?)",
                            (datetime.now().isoformat(), "behavioral_pattern",
                             json.dumps(p, ensure_ascii=False))
                        )
                self._insights.extend(patterns)
        except Exception as e:
            logger.debug(f"Insight generation skipped: {e}")

    # ── Cache lookup ──────────────────────────────────────────────────────────
    def check_cache(self, prompt: str) -> str | None:
        """Return cached response if available."""
        import hashlib
        key = hashlib.md5(prompt.lower().strip().encode()).hexdigest()[:12]
        try:
            with sqlite3.connect(self._train_db) as c:
                row = c.execute(
                    "SELECT response FROM cached_responses WHERE key=? AND hits>=2",
                    (key,)
                ).fetchone()
                if row:
                    c.execute("UPDATE cached_responses SET hits=hits+1 WHERE key=?", (key,))
                    return row[0]
        except Exception:
            pass
        return None

    # ── Report ────────────────────────────────────────────────────────────────
    def get_report(self) -> dict:
        try:
            with sqlite3.connect(self._train_db) as c:
                top_cmds = c.execute(
                    "SELECT pattern, count FROM command_freq ORDER BY count DESC LIMIT 10"
                ).fetchall()
                top_apps = c.execute(
                    "SELECT app, opens FROM app_usage ORDER BY opens DESC LIMIT 10"
                ).fetchall()
                cache_hits = c.execute(
                    "SELECT SUM(hits) FROM cached_responses"
                ).fetchone()[0] or 0
                insight_count = c.execute("SELECT COUNT(*) FROM insights").fetchone()[0]
            return {
                "top_commands": [{"cmd": r[0], "count": r[1]} for r in top_cmds],
                "top_apps":     [{"app": r[0], "opens": r[1]} for r in top_apps],
                "cache_hits":   cache_hits,
                "insights":     insight_count,
                "recent_insights": self._insights[-5:],
            }
        except Exception as e:
            return {"error": str(e)}
