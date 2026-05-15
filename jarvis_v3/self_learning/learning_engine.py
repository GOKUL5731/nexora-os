"""
JARVIS Self-Learning Engine — actually working version.
Runs as a background asyncio task. No threads needed.
Learns from every interaction stored in memory.db.
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("jarvis.learning")

# ── Positive/negative feedback signals ───────────────────────────────────────
POS = {"good","great","perfect","correct","yes","right","thanks","thank","நன்றி","சரி","👍"}
NEG = {"wrong","bad","no","incorrect","mistake","fix","redo","again","stupid","useless","👎"}


class SelfLearningEngine:
    def __init__(self, config: dict, memory):
        self.config   = config
        self.memory   = memory          # MemoryManager instance
        self.interval = config.get("learning", {}).get("interval_minutes", 30) * 60
        self.min_samples = config.get("learning", {}).get("min_samples", 5)
        self.learn_db = Path(memory.db_path).parent / "learning.db"
        self._running = False
        self._strategies: dict = {}
        self._init_db()
        self._load_strategies()

    def _init_db(self):
        with sqlite3.connect(self.learn_db) as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id TEXT PRIMARY KEY, intent TEXT, strategy TEXT,
                    wins INT DEFAULT 0, losses INT DEFAULT 0, updated TEXT
                );
                CREATE TABLE IF NOT EXISTS failures (
                    id TEXT PRIMARY KEY, pattern TEXT, count INT DEFAULT 1,
                    fix TEXT, resolved INT DEFAULT 0, last_seen TEXT
                );
                CREATE TABLE IF NOT EXISTS learning_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT, action TEXT, detail TEXT
                );
            """)

    def _load_strategies(self):
        path = Path("self_learning/strategies.json")
        if path.exists():
            try:
                with open(path) as f:
                    self._strategies = json.load(f)
            except Exception:
                self._strategies = {}

    def _save_strategies(self):
        path = Path("self_learning/strategies.json")
        path.parent.mkdir(exist_ok=True)
        with open(path, "w") as f:
            json.dump(self._strategies, f, indent=2, ensure_ascii=False)

    # ── Main loop ────────────────────────────────────────────────────────────
    async def start(self):
        self._running = True
        logger.info(f"Self-learning started. Cycle every {self.interval//60}min.")
        while self._running:
            await asyncio.sleep(self.interval)
            try:
                await self._cycle()
            except Exception as e:
                logger.error(f"Learning cycle error: {e}", exc_info=True)

    def stop(self):
        self._running = False

    async def _cycle(self):
        recent = self._recent_interactions(hours=max(1, self.interval / 3600))
        if len(recent) < 2:
            return
        logger.info(f"Learning cycle: analyzing {len(recent)} interactions")
        await self._learn_successes(recent)
        await self._learn_failures(recent)
        await self._extract_skills(recent)
        self._log("cycle", f"Analyzed {len(recent)} interactions")
        logger.info("Learning cycle complete.")

    def _recent_interactions(self, hours: float) -> list[dict]:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        try:
            with sqlite3.connect(self.memory.db_path) as c:
                rows = c.execute(
                    "SELECT user_input,jarvis_resp,outcome,timestamp FROM interactions WHERE timestamp>? ORDER BY timestamp DESC",
                    (since,)
                ).fetchall()
            return [{"input":r[0],"response":r[1],"outcome":r[2],"ts":r[3]} for r in rows]
        except Exception:
            return []

    # ── Learning methods ──────────────────────────────────────────────────────
    async def _learn_successes(self, interactions: list):
        good = [i for i in interactions if i["outcome"] == "success"]
        if len(good) < self.min_samples:
            return
        from core.llm_client import LLMClient
        llm = LLMClient(self.config)
        sample = "\n".join(f"- {i['input'][:80]}" for i in good[:8])
        try:
            raw = await llm.complete(
                f"Identify intent patterns in these successful requests:\n{sample}\n\n"
                f"Return JSON array: [{{\"intent\":\"...\",\"strategy\":\"...\",\"keywords\":[...]}}]\n"
                f"Return ONLY the JSON array.",
                temperature=0.2
            )
            raw = raw.strip().replace("```json","").replace("```","").strip()
            start, end = raw.find("["), raw.rfind("]")+1
            if start >= 0:
                patterns = json.loads(raw[start:end])
                for p in patterns:
                    key = p.get("intent","general")
                    self._strategies[key] = {
                        "strategy": p.get("strategy",""),
                        "keywords": p.get("keywords",[]),
                        "wins": self._strategies.get(key,{}).get("wins",0) + 1,
                        "losses": self._strategies.get(key,{}).get("losses",0),
                        "updated": datetime.now().isoformat(),
                    }
                self._save_strategies()
        except Exception as e:
            logger.debug(f"Success learning skipped: {e}")

    async def _learn_failures(self, interactions: list):
        bad = [i for i in interactions if i["outcome"] != "success"]
        if not bad:
            return
        for item in bad:
            pid = str(hash(item["input"][:40]))[:10]
            with sqlite3.connect(self.learn_db) as c:
                existing = c.execute("SELECT count FROM failures WHERE id=?", (pid,)).fetchone()
                if existing:
                    c.execute("UPDATE failures SET count=count+1,last_seen=? WHERE id=?",
                              (datetime.now().isoformat(), pid))
                else:
                    c.execute("INSERT INTO failures VALUES (?,?,1,NULL,0,?)",
                              (pid, item["input"][:200], datetime.now().isoformat()))

        # Fix patterns that fail > 2 times
        with sqlite3.connect(self.learn_db) as c:
            to_fix = c.execute(
                "SELECT id,pattern FROM failures WHERE count>2 AND resolved=0 LIMIT 3"
            ).fetchall()

        if not to_fix:
            return
        from core.llm_client import LLMClient
        llm = LLMClient(self.config)
        for fid, pattern in to_fix:
            try:
                fix = await llm.complete(
                    f"JARVIS keeps failing at: \"{pattern[:100]}\"\n"
                    f"Suggest a concrete 1-sentence fix strategy.",
                    temperature=0.3
                )
                with sqlite3.connect(self.learn_db) as c:
                    c.execute("UPDATE failures SET fix=?,resolved=1 WHERE id=?", (fix, fid))
                # Store as strategy
                intent = f"fix:{pattern[:30]}"
                self._strategies[intent] = {"strategy": fix, "keywords": [], "wins": 0, "losses": 1}
                self._save_strategies()
            except Exception:
                pass

    async def _extract_skills(self, interactions: list):
        good = [i for i in interactions if i["outcome"] == "success"]
        if len(good) < self.min_samples:
            return
        from core.llm_client import LLMClient
        llm = LLMClient(self.config)
        sample = "\n".join(f"Input:{i['input'][:60]}" for i in good[:6])
        try:
            raw = await llm.complete(
                f"From these interactions, identify ONE reusable skill (if any obvious pattern):\n{sample}\n\n"
                f"Return JSON: {{\"name\":\"...\",\"description\":\"...\",\"steps\":[\"step1\",\"step2\"]}}\n"
                f"If no clear pattern, return: {{\"name\":\"\"}}\nReturn ONLY JSON.",
                temperature=0.2
            )
            raw = raw.strip().replace("```json","").replace("```","").strip()
            skill = json.loads(raw)
            if skill.get("name") and skill.get("steps"):
                self.memory.store_skill(skill["name"], skill.get("description",""), skill["steps"])
                logger.info(f"Learned skill: {skill['name']}")
        except Exception:
            pass

    # ── Feedback detection ────────────────────────────────────────────────────
    def detect_feedback(self, text: str) -> str | None:
        """Returns 'positive', 'negative', or None."""
        words = set(text.lower().split())
        if len(words) > 8:
            return None   # Too long to be pure feedback
        if words & POS:
            return "positive"
        if words & NEG:
            return "negative"
        return None

    def get_strategy_hint(self, user_input: str) -> str | None:
        """Return a strategy hint for the orchestrator system prompt."""
        if not self._strategies:
            return None
        low = user_input.lower()
        best, best_score = None, 0
        for intent, data in self._strategies.items():
            kws = data.get("keywords", [])
            score = sum(1 for kw in kws if kw.lower() in low)
            score *= max(1, data.get("wins", 1))
            if score > best_score:
                best_score, best = score, data.get("strategy","")
        return best if best_score > 0 else None

    def get_summary(self) -> dict:
        total = self.memory.get_interaction_count()
        fails = 0
        with sqlite3.connect(self.learn_db) as c:
            fails = c.execute("SELECT COUNT(*) FROM failures WHERE resolved=0").fetchone()[0]
        return {
            "total_interactions": total,
            "strategies_learned": len(self._strategies),
            "unresolved_failures": fails,
        }

    def _log(self, action: str, detail: str):
        with sqlite3.connect(self.learn_db) as c:
            c.execute("INSERT INTO learning_log(ts,action,detail) VALUES(?,?,?)",
                      (datetime.now().isoformat(), action, detail[:500]))
