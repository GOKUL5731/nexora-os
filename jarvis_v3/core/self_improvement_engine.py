"""
JARVIS Phase 4 — Self-Improvement Engine
Analyze → Generate Patch → Sandbox → Test → Benchmark → Deploy → Rollback
"""
import asyncio, json, logging, re, shutil, sqlite3, subprocess, sys, time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("jarvis.self_improvement")
ROOT   = Path(__file__).resolve().parent.parent
DB     = ROOT / "database" / "improvements.db"
DB.parent.mkdir(parents=True, exist_ok=True)
SANDBOX_DIR = ROOT / "sandbox" / "improvements"
BACKUP_DIR  = ROOT / "backups"
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def _init_db():
    with sqlite3.connect(DB) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS improvements (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT,
            target_file  TEXT,
            issue        TEXT,
            patch        TEXT,
            test_result  TEXT,
            benchmark_before TEXT,
            benchmark_after  TEXT,
            status       TEXT DEFAULT 'pending',
            deployed     INTEGER DEFAULT 0,
            backup_path  TEXT
        );
        """)
_init_db()


class SelfImprovementEngine:
    """
    Controlled recursive self-improvement pipeline:
    1. Analyze code for inefficiencies / bugs
    2. Generate improved version via LLM
    3. Run in sandbox
    4. Execute tests
    5. Benchmark comparison
    6. Deploy if improvement confirmed
    7. Backup + rollback capability
    """

    # Files excluded from self-modification (safety)
    PROTECTED = {
        "core/self_improvement_engine.py",
        "core/sandbox_engine.py",
        "core/reliability_engine.py",
        "main.py",
    }

    def __init__(self, config: dict = None, orchestrator=None):
        self.config      = config or {}
        self.orchestrator = orchestrator
        self._running    = False
        try:
            from core.event_bus import get_event_bus
            from core.module_manager import get_module_manager
            self.bus = get_event_bus()
            get_module_manager().register("self_improvement", status="online", detail="Pipeline ready")
        except Exception:
            self.bus = None

    # ── Analysis ──────────────────────────────────────────────────────────────
    async def analyze_file(self, file_path: str) -> Dict:
        """Ask LLM to identify inefficiencies in a source file."""
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}
        if any(str(path).endswith(p) for p in self.PROTECTED):
            return {"error": "Protected file — self-modification blocked"}

        code = path.read_text(encoding="utf-8", errors="replace")[:6000]
        analysis = await self._think(
            f"Analyze this Python code for:\n"
            f"1. Performance bottlenecks\n2. Bug risks\n3. GPU optimization opportunities\n"
            f"4. Memory inefficiencies\n5. Better algorithms\n\n"
            f"File: {path.name}\n```python\n{code}\n```\n\n"
            f"Return JSON: {{\"issues\": [{{\"line\": N, \"type\": \"...\", \"description\": \"...\", \"severity\": \"low/medium/high\"}}], \"overall_score\": 0-100}}"
        )
        try:
            match = re.search(r'\{[\s\S]*\}', analysis)
            return json.loads(match.group()) if match else {"raw": analysis[:500]}
        except Exception:
            return {"raw": analysis[:500]}

    async def generate_improvement(self, file_path: str, issue: str = None) -> Dict:
        """Generate an improved version of a file."""
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found"}
        if any(str(path).endswith(p) for p in self.PROTECTED):
            return {"error": "Protected file"}

        original = path.read_text(encoding="utf-8", errors="replace")[:8000]
        prompt   = (
            f"Improve this Python code. Fix: {issue}\n\n"
            f"Requirements: maintain all existing functionality, improve performance,\n"
            f"use CUDA/GPU where beneficial, add proper error handling.\n\n"
            f"Return ONLY the complete improved Python file:\n```python\n{original}\n```"
        )
        improved = await self._think(prompt)

        # Extract code block
        match = re.search(r'```python\n([\s\S]*?)```', improved)
        new_code = match.group(1) if match else improved

        # Syntax check
        try:
            compile(new_code, path.name, "exec")
        except SyntaxError as e:
            return {"error": f"Generated code has syntax error: {e}", "code": new_code[:500]}

        return {"new_code": new_code, "original_path": str(path), "issue": issue}

    # ── Sandbox Execution ──────────────────────────────────────────────────────
    def _run_in_sandbox(self, code: str, timeout: int = 30) -> Dict:
        """Execute code in isolated subprocess."""
        tmp = SANDBOX_DIR / f"test_{int(time.time())}.py"
        tmp.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, str(tmp)],
                capture_output=True, text=True, timeout=timeout,
                cwd=str(ROOT)
            )
            return {
                "success": proc.returncode == 0,
                "stdout":  proc.stdout[:1000],
                "stderr":  proc.stderr[:500],
                "returncode": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout", "stderr": "Execution timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            tmp.unlink(missing_ok=True)

    # ── Benchmark ─────────────────────────────────────────────────────────────
    def _benchmark_file(self, file_path: str) -> Dict:
        """Simple benchmark: import time + basic metrics."""
        code = f"""
import time, importlib.util, sys
sys.path.insert(0, r'{ROOT}')
start = time.perf_counter()
try:
    spec = importlib.util.spec_from_file_location("mod", r'{file_path}')
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    elapsed = time.perf_counter() - start
    print(f"IMPORT_TIME:{{elapsed:.4f}}")
except Exception as e:
    print(f"ERROR:{{e}}")
"""
        result = self._run_in_sandbox(code, timeout=15)
        import_time = None
        for line in result.get("stdout", "").split('\n'):
            if line.startswith("IMPORT_TIME:"):
                try:
                    import_time = float(line.split(':')[1])
                except Exception:
                    pass
        return {"import_time_s": import_time, "success": result["success"]}

    def _run_tests_for_candidate(self, original_path: Path, candidate_path: Path) -> Dict:
        """Run syntax/import checks and the local smoke suites before deployment."""
        checks = []
        compile_proc = subprocess.run(
            [sys.executable, "-m", "py_compile", str(candidate_path)],
            capture_output=True, text=True, timeout=20, cwd=str(ROOT)
        )
        checks.append({
            "name": "py_compile",
            "ok": compile_proc.returncode == 0,
            "stdout": compile_proc.stdout[-1000:],
            "stderr": compile_proc.stderr[-1000:],
        })
        if compile_proc.returncode != 0:
            return {"success": False, "checks": checks}

        import_check = self._benchmark_file(str(candidate_path))
        checks.append({"name": "import_candidate", "ok": bool(import_check.get("success")), "result": import_check})
        if not import_check.get("success"):
            return {"success": False, "checks": checks}

        # Run the quick Core OS smoke suite. It is intentionally broad enough to
        # catch broken imports/wiring without taking over the machine.
        test_file = ROOT / "tests" / "test_core_os.py"
        if test_file.exists():
            proc = subprocess.run(
                [sys.executable, "-X", "utf8", str(test_file)],
                capture_output=True, text=True, timeout=120, cwd=str(ROOT)
            )
            checks.append({
                "name": "test_core_os",
                "ok": proc.returncode == 0,
                "stdout": proc.stdout[-2000:],
                "stderr": proc.stderr[-2000:],
            })
        return {"success": all(check.get("ok") for check in checks), "checks": checks}

    # ── Full Pipeline ──────────────────────────────────────────────────────────
    async def run_improvement_pipeline(
        self, file_path: str, issue: str = "general optimization", auto_deploy: bool = False
    ) -> Dict:
        """Execute the full improvement pipeline for one file."""
        if self._running:
            return {"error": "Improvement pipeline already running"}

        self._running = True
        path = Path(file_path)
        timestamp = datetime.now().isoformat()
        record_id = None

        try:
            logger.info(f"[SelfImprove] Starting pipeline for {path.name}")
            self._publish("self_improvement.started", {"file": str(path), "issue": issue})

            # Record in DB
            with sqlite3.connect(DB) as c:
                cursor = c.execute(
                    "INSERT INTO improvements (timestamp,target_file,issue,status) VALUES (?,?,?,?)",
                    (timestamp, str(path), issue, "analyzing")
                )
                record_id = cursor.lastrowid

            # Step 1: Benchmark original
            bench_before = self._benchmark_file(str(path))
            logger.info(f"[SelfImprove] Benchmark before: {bench_before}")
            self._publish("self_improvement.benchmark_before", bench_before)

            # Step 2: Generate improvement
            gen = await self.generate_improvement(str(path), issue)
            if "error" in gen:
                self._update_record(record_id, "failed", gen["error"])
                return gen

            new_code = gen["new_code"]
            self._update_record(record_id, "generated", patch=new_code[:500])
            self._publish("self_improvement.generated", {"record_id": record_id})

            # Step 3: Sandbox test
            sandbox_result = self._run_in_sandbox(new_code)
            self._update_record(record_id, "sandbox_tested",
                                test_result=json.dumps(sandbox_result))

            if not sandbox_result["success"]:
                self._update_record(record_id, "sandbox_failed")
                self._publish("self_improvement.failed", {"record_id": record_id, "stage": "sandbox", "result": sandbox_result})
                return {"error": "Sandbox test failed", "sandbox": sandbox_result}

            # Step 4: Save improved to temp
            tmp_path = SANDBOX_DIR / f"{path.stem}_improved.py"
            tmp_path.write_text(new_code, encoding="utf-8")

            test_result = self._run_tests_for_candidate(path, tmp_path)
            self._update_record(record_id, "tested", test_result=json.dumps(test_result))
            self._publish("self_improvement.tested", {"record_id": record_id, "success": test_result["success"]})
            if not test_result["success"]:
                tmp_path.unlink(missing_ok=True)
                self._update_record(record_id, "test_failed")
                return {"error": "Candidate tests failed", "tests": test_result, "record_id": record_id}

            # Step 5: Benchmark improved
            bench_after = self._benchmark_file(str(tmp_path))
            logger.info(f"[SelfImprove] Benchmark after: {bench_after}")
            self._publish("self_improvement.benchmark_after", bench_after)

            with sqlite3.connect(DB) as c:
                c.execute(
                    "UPDATE improvements SET benchmark_before=?, benchmark_after=? WHERE id=?",
                    (json.dumps(bench_before), json.dumps(bench_after), record_id)
                )

            # Step 6: Deploy if improved (or forced)
            improved = (
                bench_after.get("import_time_s", 999) <
                bench_before.get("import_time_s", 999) * 1.05
            )

            deployed = False
            backup_path = None

            if auto_deploy and (improved or not bench_before.get("import_time_s")):
                backup_path = BACKUP_DIR / f"{path.stem}_{int(time.time())}.bak.py"
                shutil.copy2(path, backup_path)
                shutil.copy2(tmp_path, path)
                deployed = True
                logger.info(f"[SelfImprove] Deployed improvement to {path}")
                self._update_record(record_id, "deployed", backup_path=str(backup_path))
                self._publish("self_improvement.deployed", {"record_id": record_id, "file": str(path), "backup": str(backup_path)})
            else:
                self._update_record(record_id, "ready_to_deploy")
                self._publish("self_improvement.ready", {"record_id": record_id, "improved": improved})

            tmp_path.unlink(missing_ok=True)

            return {
                "file":             str(path),
                "issue":            issue,
                "sandbox_passed":   True,
                "benchmark_before": bench_before,
                "benchmark_after":  bench_after,
                "improved":         improved,
                "deployed":         deployed,
                "backup":           str(backup_path) if backup_path else None,
                "record_id":        record_id,
                "tests":            test_result,
                "new_code":         new_code[:500] + "..." if len(new_code) > 500 else new_code,
            }

        except Exception as e:
            logger.error(f"[SelfImprove] Pipeline error: {e}", exc_info=True)
            if record_id:
                self._update_record(record_id, "error")
            self._publish("self_improvement.failed", {"record_id": record_id, "error": str(e)})
            return {"error": str(e)}
        finally:
            self._running = False

    # ── Rollback ───────────────────────────────────────────────────────────────
    def rollback(self, record_id: int) -> Dict:
        """Restore a file from its backup."""
        with sqlite3.connect(DB) as c:
            row = c.execute(
                "SELECT target_file, backup_path FROM improvements WHERE id=?", (record_id,)
            ).fetchone()
        if not row or not row[1]:
            return {"error": "No backup found for this record"}

        target, backup = Path(row[0]), Path(row[1])
        if not backup.exists():
            return {"error": f"Backup file not found: {backup}"}

        shutil.copy2(backup, target)
        with sqlite3.connect(DB) as c:
            c.execute("UPDATE improvements SET status='rolled_back', deployed=0 WHERE id=?",
                      (record_id,))
        logger.info(f"[SelfImprove] Rolled back {target.name} from {backup.name}")
        return {"rolled_back": str(target), "from_backup": str(backup)}

    def deploy_plugin_code(self, name: str, code: str, plugin_manager=None) -> Dict:
        """Compile, contract-check, backup, deploy, and reload a plugin file."""
        safe_name = re.sub(r"[^\w]", "_", name.lower()).strip("_") or "generated_plugin"
        if not safe_name.endswith("_plugin"):
            safe_name += "_plugin"
        target = ROOT / "plugins" / f"{safe_name}.py"
        tmp = SANDBOX_DIR / f"{safe_name}_candidate.py"
        tmp.write_text(code, encoding="utf-8")
        try:
            compile_proc = subprocess.run(
                [sys.executable, "-m", "py_compile", str(tmp)],
                capture_output=True, text=True, timeout=20, cwd=str(ROOT)
            )
            if compile_proc.returncode != 0:
                return {"deployed": False, "error": compile_proc.stderr[-1000:]}
            namespace: dict = {}
            exec(compile(tmp.read_text(encoding="utf-8"), str(tmp), "exec"), namespace)
            register = namespace.get("register")
            if not callable(register):
                return {"deployed": False, "error": "Plugin must define register(config)"}
            registration = register(self.config)
            if not isinstance(registration, dict) or not registration.get("tools"):
                return {"deployed": False, "error": "register(config) must return a dict with tools"}

            backup = None
            if target.exists():
                backup = BACKUP_DIR / f"{safe_name}_{int(time.time())}.bak.py"
                shutil.copy2(target, backup)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tmp, target)
            if plugin_manager:
                plugin_manager.reload_plugin(target.stem)
            self._publish("self_improvement.plugin_deployed", {"plugin": target.stem, "backup": str(backup) if backup else None})
            return {"deployed": True, "plugin": target.stem, "target": str(target), "backup": str(backup) if backup else None}
        finally:
            tmp.unlink(missing_ok=True)

    # ── Batch Analysis ─────────────────────────────────────────────────────────
    async def scan_codebase(self, directory: str = None, max_files: int = 10) -> List[Dict]:
        """Analyze all Python files in a directory and report issues."""
        target = Path(directory) if directory else ROOT / "core"
        files  = list(target.rglob("*.py"))[:max_files]
        results = []
        for f in files:
            if any(str(f).endswith(p) for p in self.PROTECTED):
                continue
            analysis = await self.analyze_file(str(f))
            score = analysis.get("overall_score", 50)
            results.append({
                "file":   str(f.relative_to(ROOT)),
                "score":  score,
                "issues": analysis.get("issues", []),
            })
        results.sort(key=lambda x: x["score"])
        return results

    def get_history(self, limit: int = 20) -> List[Dict]:
        with sqlite3.connect(DB) as c:
            rows = c.execute(
                "SELECT id,timestamp,target_file,issue,status,deployed FROM improvements "
                "ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{"id":r[0],"timestamp":r[1],"file":r[2],"issue":r[3],
                 "status":r[4],"deployed":bool(r[5])} for r in rows]

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _update_record(self, record_id: int, status: str,
                       test_result: str = None, patch: str = None, backup_path: str = None):
        with sqlite3.connect(DB) as c:
            if patch:
                c.execute("UPDATE improvements SET patch=? WHERE id=?", (patch, record_id))
            if test_result:
                c.execute("UPDATE improvements SET test_result=? WHERE id=?", (test_result, record_id))
            if backup_path:
                c.execute("UPDATE improvements SET backup_path=? WHERE id=?", (backup_path, record_id))
            c.execute("UPDATE improvements SET status=? WHERE id=?", (status, record_id))

    async def _think(self, prompt: str) -> str:
        if self.orchestrator:
            resp = await self.orchestrator.process(prompt)
            return resp.get("message", "")
        return ""

    def _publish(self, topic: str, payload: dict):
        if getattr(self, "bus", None):
            self.bus.publish(topic, payload, source="self_improvement")
