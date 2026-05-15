"""
JARVIS Phase 4 — AI LAB Core
Isolated workspace for experimentation, plugin generation, agent evolution,
model training management, and benchmarking.
"""
import asyncio, json, logging, shutil, sqlite3, subprocess, time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("jarvis.ai_lab")
ROOT   = Path(__file__).resolve().parent.parent

# AI LAB directory structure
LAB = ROOT / "AI_LAB"
for d in ["sandbox","experiments","plugins","agents","training","datasets",
          "benchmarks","deployments","failed_attempts","evolutionary_models"]:
    (LAB / d).mkdir(parents=True, exist_ok=True)

DB = ROOT / "database" / "ai_lab.db"
DB.parent.mkdir(parents=True, exist_ok=True)

def _init_db():
    with sqlite3.connect(DB) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS experiments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            type        TEXT,
            status      TEXT DEFAULT 'pending',
            config      TEXT DEFAULT '{}',
            result      TEXT DEFAULT '{}',
            created     TEXT,
            completed   TEXT,
            score       REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS benchmarks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            timestamp   TEXT,
            metrics     TEXT,
            system_info TEXT
        );
        CREATE TABLE IF NOT EXISTS lab_plugins (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE,
            code        TEXT,
            status      TEXT DEFAULT 'draft',
            created     TEXT,
            deployed    INTEGER DEFAULT 0
        );
        """)
_init_db()


class AILabCore:
    """
    AI Laboratory: isolated experimentation, plugin/agent generation,
    evolutionary model management, and benchmarking.
    """

    def __init__(self, config: dict = None, orchestrator=None,
                 agent_manager=None, self_improve=None):
        self.config       = config or {}
        self.orchestrator = orchestrator
        self.agents       = agent_manager
        self.improver     = self_improve
        self._active_experiments: Dict[int, asyncio.Task] = {}

    # ── Experiments ────────────────────────────────────────────────────────────
    def create_experiment(self, name: str, exp_type: str, config: dict = None) -> int:
        """Register a new experiment."""
        with sqlite3.connect(DB) as c:
            cursor = c.execute(
                "INSERT INTO experiments (name,type,config,status,created) VALUES (?,?,?,?,?)",
                (name, exp_type, json.dumps(config or {}), "pending", datetime.now().isoformat())
            )
            return cursor.lastrowid

    async def run_experiment(self, experiment_id: int) -> Dict:
        """Execute an experiment by ID."""
        with sqlite3.connect(DB) as c:
            row = c.execute(
                "SELECT name,type,config FROM experiments WHERE id=?", (experiment_id,)
            ).fetchone()
        if not row:
            return {"error": f"Experiment {experiment_id} not found"}

        name, exp_type, config_str = row
        config = json.loads(config_str)
        logger.info(f"[AILab] Running experiment {experiment_id}: {name} ({exp_type})")

        self._set_status(experiment_id, "running")
        try:
            if exp_type == "code_generation":
                result = await self._run_code_gen_experiment(name, config)
            elif exp_type == "plugin_generation":
                result = await self._run_plugin_gen_experiment(name, config)
            elif exp_type == "agent_generation":
                result = await self._run_agent_gen_experiment(name, config)
            elif exp_type == "prompt_optimization":
                result = await self._run_prompt_optimization(name, config)
            elif exp_type == "model_benchmark":
                result = await self._run_model_benchmark(name, config)
            else:
                result = await self._run_generic_experiment(name, exp_type, config)

            score = result.get("score", 0)
            self._set_status(experiment_id, "completed", result, score)
            return {"experiment_id": experiment_id, "name": name, "result": result}

        except Exception as e:
            logger.error(f"[AILab] Experiment {experiment_id} failed: {e}")
            self._set_status(experiment_id, "failed", {"error": str(e)})
            # Move to failed_attempts
            return {"error": str(e), "experiment_id": experiment_id}

    # ── Experiment Types ───────────────────────────────────────────────────────
    async def _run_code_gen_experiment(self, name: str, config: dict) -> Dict:
        prompt     = config.get("prompt", "Generate a useful Python utility function")
        iterations = config.get("iterations", 3)
        best_code  = ""
        best_score = 0

        for i in range(iterations):
            code = await self._think(
                f"Iteration {i+1}/{iterations}: {prompt}\n"
                f"Return ONLY working Python code, no explanation."
            )
            match = __import__("re").search(r'```python\n([\s\S]*?)```', code)
            code  = match.group(1) if match else code

            # Test it
            result = self._sandbox_run(code)
            score  = 100 if result["success"] else 0
            if score > best_score:
                best_score = score
                best_code  = code

        # Save best result
        out_file = LAB / "experiments" / f"{name}_{int(time.time())}.py"
        out_file.write_text(best_code, encoding="utf-8")
        return {"best_code": best_code[:500], "score": best_score, "iterations": iterations}

    async def _run_plugin_gen_experiment(self, name: str, config: dict) -> Dict:
        description = config.get("description", "A useful JARVIS plugin")
        plugin_code = await self._generate_plugin_code(description)
        result      = self._sandbox_run(plugin_code)
        score       = 80 if result["success"] else 20

        # Save
        with sqlite3.connect(DB) as c:
            c.execute(
                "INSERT OR REPLACE INTO lab_plugins (name,code,status,created) VALUES (?,?,?,?)",
                (name, plugin_code, "tested" if result["success"] else "failed",
                 datetime.now().isoformat())
            )
        out = LAB / "plugins" / f"{name}.py"
        out.write_text(plugin_code, encoding="utf-8")
        return {"plugin": name, "sandbox_passed": result["success"], "score": score}

    async def _run_agent_gen_experiment(self, name: str, config: dict) -> Dict:
        description = config.get("description", "A helpful AI agent")
        if self.agents:
            from core.agent_builder import AgentBuilder
            builder = AgentBuilder(self.orchestrator, self.agents)
            result  = await builder.build_agent(description, name)
            result["score"] = 90 if result.get("registered") else 40
            # Save copy to lab
            (LAB / "agents" / f"{name}_agent.py").write_text(
                builder.get_agent_code(name), encoding="utf-8"
            )
            return result
        return {"error": "AgentManager not available", "score": 0}

    async def _run_prompt_optimization(self, name: str, config: dict) -> Dict:
        base_prompt = config.get("base_prompt", "Answer helpfully")
        test_inputs = config.get("test_inputs", ["Hello", "What time is it?"])
        variants    = []

        for i in range(3):
            optimized = await self._think(
                f"Rewrite this system prompt to be more effective (variant {i+1}):\n{base_prompt}"
            )
            variants.append({"variant": i+1, "prompt": optimized[:200]})

        out = LAB / "experiments" / f"{name}_prompts.json"
        out.write_text(json.dumps(variants, indent=2), encoding="utf-8")
        return {"variants": variants, "score": 70}

    async def _run_model_benchmark(self, name: str, config: dict) -> Dict:
        prompts  = config.get("prompts", ["What is 2+2?", "Write hello world in Python"])
        results  = []
        for p in prompts[:5]:
            t0   = time.perf_counter()
            resp = await self._think(p)
            lat  = round((time.perf_counter() - t0) * 1000, 1)
            results.append({"prompt": p[:50], "latency_ms": lat, "response_len": len(resp)})

        avg_lat = sum(r["latency_ms"] for r in results) / max(len(results), 1)
        score   = max(0, 100 - int(avg_lat / 50))

        # Save benchmark
        metrics = {"name": name, "avg_latency_ms": avg_lat, "results": results}
        with sqlite3.connect(DB) as c:
            c.execute(
                "INSERT INTO benchmarks (name,timestamp,metrics) VALUES (?,?,?)",
                (name, datetime.now().isoformat(), json.dumps(metrics))
            )
        return {"avg_latency_ms": avg_lat, "runs": len(results), "score": score}

    async def _run_generic_experiment(self, name: str, exp_type: str, config: dict) -> Dict:
        description = config.get("description", f"Run experiment: {exp_type}")
        result = await self._think(f"Execute this AI experiment and report findings:\n{description}")
        out = LAB / "experiments" / f"{name}_{exp_type}.txt"
        out.write_text(result, encoding="utf-8")
        return {"result": result[:500], "score": 50}

    # ── Plugin Generation ──────────────────────────────────────────────────────
    async def generate_plugin(self, description: str, name: str = None) -> Dict:
        """Generate and save a JARVIS plugin to AI_LAB/plugins/."""
        if not name:
            name = description.lower()[:20].replace(' ', '_').strip('_')
        code = await self._generate_plugin_code(description)
        result = self._sandbox_run(code)

        status = "tested" if result["success"] else "sandbox_failed"
        out    = LAB / "plugins" / f"{name}.py"
        out.write_text(code, encoding="utf-8")

        with sqlite3.connect(DB) as c:
            c.execute(
                "INSERT OR REPLACE INTO lab_plugins (name,code,status,created) VALUES (?,?,?,?)",
                (name, code, status, datetime.now().isoformat())
            )

        return {
            "name":           name,
            "file":           str(out),
            "sandbox_passed": result["success"],
            "status":         status,
        }

    async def deploy_plugin(self, name: str) -> Dict:
        """Move a tested plugin from AI_LAB to the live plugins directory."""
        src = LAB / "plugins" / f"{name}.py"
        if not src.exists():
            return {"error": f"Plugin not found: {name}"}

        dst = ROOT / "plugins" / f"{name}.py"
        shutil.copy2(src, dst)

        with sqlite3.connect(DB) as c:
            c.execute("UPDATE lab_plugins SET deployed=1, status='deployed' WHERE name=?", (name,))

        # Move to deployments log
        shutil.copy2(src, LAB / "deployments" / f"{name}_{int(time.time())}.py")
        return {"deployed": True, "name": name, "path": str(dst)}

    async def _generate_plugin_code(self, description: str) -> str:
        code = await self._think(
            f"Generate a complete JARVIS plugin Python file for: {description}\n\n"
            f"The plugin must define:\n"
            f"  PLUGIN_NAME = 'plugin_name'\n"
            f"  PLUGIN_VERSION = '1.0.0'\n"
            f"  async def execute(command: str, context: dict) -> dict: ...\n\n"
            f"Return ONLY the Python code, no explanation."
        )
        match = __import__("re").search(r'```python\n([\s\S]*?)```', code)
        return match.group(1) if match else code

    # ── Benchmarking ───────────────────────────────────────────────────────────
    async def run_system_benchmark(self) -> Dict:
        """Benchmark the full JARVIS system."""
        import psutil
        metrics = {
            "timestamp":   datetime.now().isoformat(),
            "cpu_count":   psutil.cpu_count(),
            "ram_gb":      round(psutil.virtual_memory().total / 1e9, 1),
        }

        # GPU info
        try:
            import torch
            metrics["cuda"] = torch.cuda.is_available()
            if metrics["cuda"]:
                metrics["gpu"] = torch.cuda.get_device_name(0)
                metrics["vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)
        except ImportError:
            metrics["cuda"] = False

        # LLM latency test
        if self.orchestrator:
            t0   = time.perf_counter()
            resp = await self.orchestrator.process("Say: BENCHMARK_OK")
            lat  = round((time.perf_counter() - t0) * 1000, 1)
            metrics["llm_latency_ms"] = lat
            metrics["llm_responsive"] = "BENCHMARK_OK" in resp.get("message", "")

        with sqlite3.connect(DB) as c:
            c.execute(
                "INSERT INTO benchmarks (name,timestamp,metrics) VALUES (?,?,?)",
                ("system_benchmark", datetime.now().isoformat(), json.dumps(metrics))
            )
        return metrics

    # ── List / History ─────────────────────────────────────────────────────────
    def list_experiments(self, limit: int = 20) -> List[Dict]:
        with sqlite3.connect(DB) as c:
            rows = c.execute(
                "SELECT id,name,type,status,score,created FROM experiments "
                "ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{"id":r[0],"name":r[1],"type":r[2],"status":r[3],
                 "score":r[4],"created":r[5]} for r in rows]

    def list_plugins(self) -> List[Dict]:
        with sqlite3.connect(DB) as c:
            rows = c.execute(
                "SELECT name,status,created,deployed FROM lab_plugins ORDER BY id DESC"
            ).fetchall()
        return [{"name":r[0],"status":r[1],"created":r[2],"deployed":bool(r[3])} for r in rows]

    def get_benchmarks(self, limit: int = 10) -> List[Dict]:
        with sqlite3.connect(DB) as c:
            rows = c.execute(
                "SELECT name,timestamp,metrics FROM benchmarks ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [{"name":r[0],"timestamp":r[1],"metrics":json.loads(r[2])} for r in rows]

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _set_status(self, exp_id: int, status: str, result: dict = None, score: float = 0):
        with sqlite3.connect(DB) as c:
            if result:
                c.execute(
                    "UPDATE experiments SET status=?, result=?, score=?, completed=? WHERE id=?",
                    (status, json.dumps(result), score, datetime.now().isoformat(), exp_id)
                )
            else:
                c.execute("UPDATE experiments SET status=? WHERE id=?", (status, exp_id))

    def _sandbox_run(self, code: str, timeout: int = 15) -> Dict:
        tmp = LAB / "sandbox" / f"tmp_{int(time.time())}.py"
        tmp.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                ["python", str(tmp)], capture_output=True, text=True,
                timeout=timeout, cwd=str(ROOT)
            )
            return {"success": proc.returncode == 0, "stdout": proc.stdout[:500],
                    "stderr": proc.stderr[:300]}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            tmp.unlink(missing_ok=True)

    async def _think(self, prompt: str) -> str:
        if self.orchestrator:
            resp = await self.orchestrator.process(prompt)
            return resp.get("message", "")
        return ""
