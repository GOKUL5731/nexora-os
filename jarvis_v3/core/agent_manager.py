"""
JARVIS Phase 3 — Agent Manager
Manages lifecycle of all AI agents: spawn, run, communicate, monitor.
"""
import asyncio, json, logging, sqlite3, threading, time, uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger("jarvis.agent_manager")
ROOT   = Path(__file__).resolve().parent.parent
DB     = ROOT / "database" / "agents.db"
DB.parent.mkdir(parents=True, exist_ok=True)

def _init_db():
    with sqlite3.connect(DB) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            id        TEXT PRIMARY KEY,
            name      TEXT UNIQUE NOT NULL,
            type      TEXT NOT NULL,
            status    TEXT DEFAULT 'idle',
            spec      TEXT DEFAULT '{}',
            created   TEXT,
            last_used TEXT,
            run_count INTEGER DEFAULT 0,
            memory    TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS agent_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id   TEXT,
            timestamp  TEXT,
            event      TEXT,
            data       TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent TEXT,
            to_agent   TEXT,
            timestamp  TEXT,
            content    TEXT,
            read       INTEGER DEFAULT 0
        );
        """)
_init_db()


class BaseAgent:
    """Base class all JARVIS agents inherit from."""

    def __init__(self, name: str, agent_type: str, config: dict = None, orchestrator=None):
        self.name          = name
        self.type          = agent_type
        self.config        = config or {}
        self.orchestrator  = orchestrator
        self.memory: Dict  = {}
        self.status        = "idle"
        self._id           = str(uuid.uuid4())[:8]
        self.task_queue: List[Dict[str, Any]] = []

    async def execute(self, task: str, context: dict = None) -> Dict:
        raise NotImplementedError

    async def think(self, prompt: str) -> str:
        """Ask the LLM for reasoning."""
        if self.orchestrator:
            resp = await self.orchestrator.process(prompt)
            return resp.get("message", "")
        return ""

    def remember(self, key: str, value: Any):
        self.memory[key] = value
        with sqlite3.connect(DB) as c:
            c.execute("UPDATE agents SET memory=? WHERE name=?",
                      (json.dumps(self.memory), self.name))

    def recall(self, key: str, default=None):
        return self.memory.get(key, default)

    def log(self, event: str, data: Any = None):
        with sqlite3.connect(DB) as c:
            c.execute("INSERT INTO agent_logs (agent_id,timestamp,event,data) VALUES (?,?,?,?)",
                      (self.name, datetime.now().isoformat(), event, json.dumps(data or {})))

    def enqueue(self, task: str, context: dict = None) -> str:
        task_id = str(uuid.uuid4())[:8]
        self.task_queue.append({"id": task_id, "task": task, "context": context or {}, "created": datetime.now().isoformat()})
        self.log("task_queued", {"task_id": task_id, "task": task})
        return task_id

    def dequeue(self) -> Optional[Dict[str, Any]]:
        if not self.task_queue:
            return None
        return self.task_queue.pop(0)


class CommanderAgent(BaseAgent):
    """Coordinates multi-agent task pipelines."""

    def __init__(self, config=None, orchestrator=None, manager=None):
        super().__init__("commander", "commander", config, orchestrator)
        self.manager = manager

    async def execute(self, task: str, context: dict = None) -> Dict:
        self.log("task_received", {"task": task})
        plan = await self.think(
            f"Break this task into sub-tasks for specialized agents:\n"
            f"Task: {task}\n\n"
            f"Available agents: planner, coder, researcher, tester, optimizer\n"
            f"Return a JSON list: [{{\"agent\": \"...\", \"subtask\": \"...\"}}]"
        )
        try:
            import re
            match = re.search(r'\[[\s\S]*\]', plan)
            steps = json.loads(match.group()) if match else []
        except Exception:
            steps = [{"agent": "planner", "subtask": task}]

        results = []
        for step in steps[:5]:  # limit
            agent_name = step.get("agent", "planner")
            subtask    = step.get("subtask", task)
            if self.manager:
                result = await self.manager.run_agent(agent_name, subtask, context)
                results.append({"agent": agent_name, "subtask": subtask, "result": result})

        self.log("task_complete", {"steps": len(results)})
        return {"commander_result": results, "original_task": task}


class PlannerAgent(BaseAgent):
    """Breaks complex goals into ordered execution plans."""

    def __init__(self, config=None, orchestrator=None):
        super().__init__("planner", "planner", config, orchestrator)

    async def execute(self, task: str, context: dict = None) -> Dict:
        self.log("planning", {"task": task})
        plan_text = await self.think(
            f"Create a numbered step-by-step execution plan for: {task}\n"
            f"Be specific and actionable. Each step should be executable by JARVIS."
        )
        steps = [s.strip() for s in plan_text.split("\n") if s.strip() and s[0].isdigit()]
        return {"plan": steps, "task": task, "step_count": len(steps)}


class ResearchAgent(BaseAgent):
    """Collects and summarizes information on topics."""

    def __init__(self, config=None, orchestrator=None):
        super().__init__("researcher", "research", config, orchestrator)

    async def execute(self, task: str, context: dict = None) -> Dict:
        self.log("researching", {"topic": task})
        summary = await self.think(
            f"Research and summarize everything important about: {task}\n"
            f"Structure: Overview, Key Points, Applications, Limitations"
        )
        self.remember("last_research_topic", task)
        return {"summary": summary, "topic": task}


class CodingAgent(BaseAgent):
    """Writes, debugs, tests, and refactors code using the existing CodingCopilot."""

    def __init__(self, config=None, orchestrator=None):
        super().__init__("coder", "coding", config, orchestrator)

    async def execute(self, task: str, context: dict = None) -> Dict:
        context = context or {}
        self.log("coding", {"task": task})
        from core.coder import CodingCopilot
        router = getattr(self.orchestrator, "router", None)
        copilot = CodingCopilot(self.config, router)
        mode = context.get("mode", "write")
        code = context.get("code", "")
        if mode == "run":
            return await copilot.run(code or task, context.get("language", "python"), context.get("timeout", 30))
        if mode == "debug":
            return await copilot.debug(code or task, context.get("language", "python"))
        if mode == "explain":
            return await copilot.explain(code or task)
        if mode == "refactor":
            return await copilot.refactor(code or task, context.get("goal", "improve readability"))
        if mode == "tests":
            return await copilot.generate_tests(code or task)
        return await copilot.write(task, context.get("language", "python"), context.get("save_to"))


class VisionManagerAgent(BaseAgent):
    """Runs live vision tasks through the existing VisionEngine."""

    def __init__(self, config=None, orchestrator=None):
        super().__init__("vision", "vision", config, orchestrator)

    async def execute(self, task: str, context: dict = None) -> Dict:
        context = context or {}
        self.log("vision_task", {"task": task, "mode": context.get("mode")})
        from core.vision import VisionEngine
        vision = VisionEngine(self.config)
        mode = context.get("mode", "describe_screen")
        if mode == "ocr_screen":
            return await vision.ocr_screen()
        if mode == "ocr_file":
            return await vision.ocr_file(context["path"])
        if mode == "detect_objects":
            return await vision.detect_objects(context.get("path"), context.get("confidence", 0.5))
        if mode == "detect_faces":
            return await vision.detect_faces(context.get("path"))
        if mode == "webcam":
            return await vision.capture_webcam(context.get("camera", 0))
        if mode == "windows":
            return await vision.list_visible_windows()
        llm = getattr(self.orchestrator, "llm", None)
        return await vision.describe_screen(llm)


class TestingAgent(BaseAgent):
    """Runs tests and validates code/outputs."""

    def __init__(self, config=None, orchestrator=None):
        super().__init__("tester", "testing", config, orchestrator)

    async def execute(self, task: str, context: dict = None) -> Dict:
        code = context.get("code", "") if context else ""
        self.log("testing", {"code_len": len(code)})

        if code:
            # Run code in isolated subprocess
            import subprocess, tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                            delete=False, dir=ROOT/"sandbox") as f:
                f.write(code)
                tmp = f.name
            try:
                proc = subprocess.run(
                    ["python", tmp], capture_output=True, text=True, timeout=15
                )
                success = proc.returncode == 0
                return {
                    "tested": True,
                    "success": success,
                    "stdout": proc.stdout[:500],
                    "stderr": proc.stderr[:300],
                }
            except subprocess.TimeoutExpired:
                return {"tested": True, "success": False, "error": "Timeout"}
            finally:
                Path(tmp).unlink(missing_ok=True)

        # LLM-based review
        review = await self.think(f"Review and identify issues with: {task}")
        return {"review": review, "task": task}


class OptimizationAgent(BaseAgent):
    """Analyzes and improves performance."""

    def __init__(self, config=None, orchestrator=None):
        super().__init__("optimizer", "optimization", config, orchestrator)

    async def execute(self, task: str, context: dict = None) -> Dict:
        code = context.get("code", "") if context else ""
        self.log("optimizing", {"task": task})
        prompt = (
            f"Optimize this code for performance, readability, and GPU efficiency:\n{code}"
            if code else
            f"Suggest optimizations for: {task}"
        )
        result = await self.think(prompt)
        return {"optimized": result, "task": task}


class WorkflowAgent(BaseAgent):
    """Creates and runs automation workflows through the workflow engine."""

    def __init__(self, config=None, orchestrator=None):
        super().__init__("workflow", "workflow", config, orchestrator)
        self._engine = None

    def _workflow_engine(self):
        if self._engine is None:
            from core.workflow_engine import WorkflowEngine
            self._engine = WorkflowEngine(self.orchestrator)
        return self._engine

    async def execute(self, task: str, context: dict = None) -> Dict:
        context = context or {}
        self.log("workflow_task", {"task": task, "context": context})
        engine = self._workflow_engine()
        mode = context.get("mode", "run")

        if mode == "list":
            return {"workflows": engine.list_workflows()}

        if mode == "generate":
            result = await engine.generate_workflow_from_description(task, self.orchestrator)
            spec = result.get("spec")
            if spec and context.get("save", True):
                engine.save_workflow(spec)
            return result

        workflow_name = context.get("workflow") or task.strip()
        if not engine.get_workflow(workflow_name):
            generated = await engine.generate_workflow_from_description(task, self.orchestrator)
            spec = generated.get("spec")
            if not spec:
                return generated
            engine.save_workflow(spec)
            workflow_name = spec.get("name", workflow_name)

        return await engine.run(workflow_name, context.get("variables") or {})


class DeploymentAgent(BaseAgent):
    """Safely deploys code/plugin changes."""

    def __init__(self, config=None, orchestrator=None):
        super().__init__("deployer", "deployment", config, orchestrator)

    async def execute(self, task: str, context: dict = None) -> Dict:
        code     = context.get("code", "") if context else ""
        target   = context.get("target_file", "") if context else ""
        self.log("deploying", {"target": target})

        if not code or not target:
            return {"deployed": False, "error": "Need code and target_file in context"}

        target_path = Path(target)
        backup_path = target_path.with_suffix(f".bak_{int(time.time())}")

        # Backup → Deploy
        if target_path.exists():
            import shutil
            shutil.copy2(target_path, backup_path)

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(code)
        self.log("deployed", {"target": target, "backup": str(backup_path)})
        return {
            "deployed": True,
            "target":   target,
            "backup":   str(backup_path),
        }


# ── Agent Manager ─────────────────────────────────────────────────────────────────
class AgentManager:
    """
    Lifecycle manager for all JARVIS agents.
    Supports built-in and dynamically generated agents.
    """

    def __init__(self, config: dict = None, orchestrator=None):
        self.config      = config or {}
        self.orchestrator = orchestrator
        self._agents: Dict[str, BaseAgent] = {}
        self._aliases: Dict[str, str] = {
            "coding": "coder",
            "research": "researcher",
            "testing": "tester",
            "optimization": "optimizer",
        }
        self._register_builtin()

    def _register_builtin(self):
        orc = self.orchestrator
        builtin = [
            CommanderAgent(self.config, orc, self),
            PlannerAgent(self.config, orc),
            CodingAgent(self.config, orc),
            VisionManagerAgent(self.config, orc),
            WorkflowAgent(self.config, orc),
            ResearchAgent(self.config, orc),
            TestingAgent(self.config, orc),
            OptimizationAgent(self.config, orc),
            DeploymentAgent(self.config, orc),
        ]
        for agent in builtin:
            self._agents[agent.name] = agent
            self._persist_agent(agent)
        logger.info(f"[AgentManager] {len(builtin)} built-in agents registered")
        self._publish_state()

    def _persist_agent(self, agent: BaseAgent):
        with sqlite3.connect(DB) as c:
            c.execute(
                "INSERT OR IGNORE INTO agents (id,name,type,status,created) VALUES (?,?,?,?,?)",
                (agent._id, agent.name, agent.type, "idle", datetime.now().isoformat())
            )

    async def run_agent(self, name: str, task: str, context: dict = None) -> Dict:
        canonical = self._aliases.get(name, name)
        agent = self._agents.get(canonical)
        if not agent:
            return {"error": f"Agent '{name}' not found. Available: {list(self._agents)}"}

        agent.enqueue(task, context)
        queued = agent.dequeue()
        task = queued["task"] if queued else task
        context = queued["context"] if queued else context
        agent.status = "running"
        self._publish_event("agent.started", {"agent": canonical, "task": task})
        with sqlite3.connect(DB) as c:
            c.execute("UPDATE agents SET status='running', last_used=?, run_count=run_count+1 WHERE name=?",
                      (datetime.now().isoformat(), canonical))
        try:
            result = await agent.execute(task, context)
            agent.status = "idle"
            with sqlite3.connect(DB) as c:
                c.execute("UPDATE agents SET status='idle' WHERE name=?", (canonical,))
            self._publish_event("agent.completed", {"agent": canonical, "result": result})
            self._publish_state()
            return result
        except Exception as e:
            agent.status = "error"
            logger.error(f"[AgentManager] Agent '{canonical}' error: {e}")
            agent.log("error", {"error": str(e)})
            self._publish_event("agent.failed", {"agent": canonical, "error": str(e)})
            self._publish_state()
            return {"error": str(e), "agent": canonical}

    async def run_team(self, task: str, context: dict = None) -> Dict:
        """Route task through Commander → multi-agent pipeline."""
        return await self.run_agent("commander", task, context)

    def list_agents(self) -> List[Dict]:
        with sqlite3.connect(DB) as c:
            rows = c.execute(
                "SELECT name,type,status,last_used,run_count FROM agents"
            ).fetchall()
        return [{"name":r[0],"type":r[1],"status":r[2],"last_used":r[3],"runs":r[4]}
                for r in rows]

    def get_agent_logs(self, name: str, limit: int = 30) -> List[Dict]:
        with sqlite3.connect(DB) as c:
            rows = c.execute(
                "SELECT timestamp,event,data FROM agent_logs WHERE agent_id=? ORDER BY id DESC LIMIT ?",
                (name, limit)
            ).fetchall()
        return [{"timestamp":r[0],"event":r[1],"data":json.loads(r[2])} for r in rows]

    def send_message(self, from_agent: str, to_agent: str, content: str):
        with sqlite3.connect(DB) as c:
            c.execute(
                "INSERT INTO messages (from_agent,to_agent,timestamp,content) VALUES (?,?,?,?)",
                (from_agent, to_agent, datetime.now().isoformat(), content)
            )
        self._publish_event("agent.message", {"from": from_agent, "to": to_agent, "content": content})

    def get_messages(self, agent_name: str) -> List[Dict]:
        with sqlite3.connect(DB) as c:
            rows = c.execute(
                "SELECT id,from_agent,timestamp,content FROM messages WHERE to_agent=? AND read=0",
                (agent_name,)
            ).fetchall()
            if rows:
                ids = [r[0] for r in rows]
                c.execute(f"UPDATE messages SET read=1 WHERE id IN ({','.join('?'*len(ids))})", ids)
        return [{"from":r[1],"timestamp":r[2],"content":r[3]} for r in rows]

    def register_agent(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent
        self._persist_agent(agent)
        self._publish_state()

    def _publish_state(self) -> None:
        try:
            from core.event_bus import get_event_bus
            from core.module_manager import get_module_manager
            agents = self.list_agents()
            get_event_bus().set_state("agents", agents, source="agent_manager")
            get_module_manager().register("agent_manager", status="online", detail=f"{len(self._agents)} agents")
        except Exception:
            pass

    def _publish_event(self, topic: str, payload: dict) -> None:
        try:
            from core.event_bus import get_event_bus
            get_event_bus().publish(topic, payload, source="agent_manager")
        except Exception:
            pass
