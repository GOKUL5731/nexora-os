"""
JARVIS Phase 3 — Workflow Engine
n8n-style trigger → condition → action automation pipelines.
"""
import asyncio, json, logging, sqlite3, threading, time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("jarvis.workflow")
ROOT   = Path(__file__).resolve().parent.parent
DB     = ROOT / "database" / "workflows.db"
DB.parent.mkdir(parents=True, exist_ok=True)

# ── Schema ──────────────────────────────────────────────────────────────────────
def _init_db():
    with sqlite3.connect(DB) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS workflows (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT UNIQUE NOT NULL,
            enabled  INTEGER DEFAULT 1,
            spec     TEXT NOT NULL,       -- JSON workflow definition
            created  TEXT,
            last_run TEXT,
            run_count INTEGER DEFAULT 0,
            last_status TEXT DEFAULT 'never'
        );
        CREATE TABLE IF NOT EXISTS runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER,
            started     TEXT,
            finished    TEXT,
            status      TEXT,
            log         TEXT
        );
        """)

_init_db()

# ── Built-in Action Handlers ─────────────────────────────────────────────────────
_ACTION_REGISTRY: Dict[str, Callable] = {}

def register_action(name: str):
    def _dec(fn):
        _ACTION_REGISTRY[name] = fn
        return fn
    return _dec

@register_action("log")
async def _act_log(params: dict, ctx: dict) -> dict:
    msg = params.get("message", "")
    logger.info(f"[Workflow] LOG: {msg}")
    return {"logged": msg}

@register_action("notify")
async def _act_notify(params: dict, ctx: dict) -> dict:
    msg = params.get("message", "")
    try:
        from plyer import notification
        notification.notify(title="JARVIS", message=msg, timeout=4)
    except Exception:
        logger.info(f"[Workflow] NOTIFY: {msg}")
    return {"notified": msg}

@register_action("run_command")
async def _act_run_cmd(params: dict, ctx: dict) -> dict:
    import subprocess
    cmd  = params.get("command", "")
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await asyncio.wait_for(proc.communicate(), timeout=30)
    return {"stdout": out.decode()[:500], "returncode": proc.returncode}

@register_action("open_app")
async def _act_open_app(params: dict, ctx: dict) -> dict:
    import subprocess
    app = params.get("app", "")
    subprocess.Popen(app, shell=True)
    return {"opened": app}

@register_action("llm_query")
async def _act_llm(params: dict, ctx: dict) -> dict:
    prompt = params.get("prompt", "")
    orc    = ctx.get("orchestrator")
    if orc:
        resp = await orc.process(prompt)
        return {"response": resp.get("message", "")}
    return {"response": "No orchestrator available"}

@register_action("file_operation")
async def _act_file(params: dict, ctx: dict) -> dict:
    op   = params.get("op", "read")
    path = params.get("path", "")
    if op == "read":
        return {"content": Path(path).read_text(errors="replace")[:2000]}
    elif op == "write":
        Path(path).write_text(params.get("content", ""))
        return {"written": path}
    elif op == "delete":
        Path(path).unlink(missing_ok=True)
        return {"deleted": path}
    return {"error": f"Unknown op: {op}"}

@register_action("http_request")
async def _act_http(params: dict, ctx: dict) -> dict:
    import urllib.request, urllib.parse
    url  = params.get("url", "")
    data = params.get("body")
    req  = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return {"status": r.status, "body": r.read().decode()[:1000]}

@register_action("wait")
async def _act_wait(params: dict, ctx: dict) -> dict:
    secs = float(params.get("seconds", 1))
    await asyncio.sleep(min(secs, 300))
    return {"waited": secs}

@register_action("set_variable")
async def _act_set_var(params: dict, ctx: dict) -> dict:
    ctx.setdefault("variables", {})[params["name"]] = params["value"]
    return {"set": params["name"]}

@register_action("condition_branch")
async def _act_condition(params: dict, ctx: dict) -> dict:
    expr = params.get("expression", "True")
    variables = ctx.get("variables", {})
    try:
        result = bool(eval(expr, {"__builtins__": {}}, variables))
    except Exception as e:
        result = False
    return {"result": result, "branch": "true" if result else "false"}


# ── Workflow Step Executor ────────────────────────────────────────────────────────
async def _execute_step(step: dict, ctx: dict) -> dict:
    action = step.get("action", "")
    params = _render_params(step.get("params", {}), ctx)
    handler = _ACTION_REGISTRY.get(action)
    if not handler:
        return {"error": f"Unknown action: {action}"}
    try:
        return await handler(params, ctx)
    except Exception as e:
        logger.error(f"[Workflow] Step '{action}' failed: {e}")
        return {"error": str(e)}


def _render_params(value: Any, ctx: dict) -> Any:
    """Render simple {{variables.x}} and {{result}} placeholders in params."""
    if isinstance(value, dict):
        return {k: _render_params(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_render_params(v, ctx) for v in value]
    if not isinstance(value, str):
        return value
    rendered = value
    for key, val in ctx.get("variables", {}).items():
        rendered = rendered.replace(f"{{{{variables.{key}}}}}", str(val))
    if "last_result" in ctx:
        rendered = rendered.replace("{{result}}", json.dumps(ctx["last_result"], ensure_ascii=False, default=str))
    return rendered


# ── Workflow Engine ───────────────────────────────────────────────────────────────
class WorkflowEngine:
    """
    Execute named automation workflows defined as JSON step sequences.

    Workflow spec format:
    {
        "name": "my_workflow",
        "description": "...",
        "steps": [
            {"action": "log",       "params": {"message": "Starting"}},
            {"action": "open_app",  "params": {"app": "notepad"}},
            {"action": "wait",      "params": {"seconds": 2}},
            {"action": "notify",    "params": {"message": "Done!"}}
        ]
    }
    """

    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self._running: Dict[str, bool] = {}
        try:
            from core.event_bus import get_event_bus
            from core.module_manager import get_module_manager
            self.bus = get_event_bus()
            get_module_manager().register("workflow_engine", status="online", detail="Workflow runtime ready")
            self._publish_state()
        except Exception:
            self.bus = None

    # ── CRUD ──────────────────────────────────────────────────────────────────
    def save_workflow(self, spec: dict) -> int:
        name = spec.get("name", f"workflow_{int(time.time())}")
        with sqlite3.connect(DB) as c:
            existing = c.execute("SELECT id FROM workflows WHERE name=?", (name,)).fetchone()
            now = datetime.now().isoformat()
            if existing:
                c.execute("UPDATE workflows SET spec=?, enabled=1 WHERE id=?",
                          (json.dumps(spec), existing[0]))
                workflow_id = existing[0]
                existing = None
                self._publish_state()
                return workflow_id
            cursor = c.execute(
                "INSERT INTO workflows (name, spec, created, last_status) VALUES (?,?,?,?)",
                (name, json.dumps(spec), now, "never")
            )
            workflow_id = cursor.lastrowid
        self._publish_state()
        return workflow_id

    def delete_workflow(self, name: str) -> bool:
        with sqlite3.connect(DB) as c:
            c.execute("DELETE FROM workflows WHERE name=?", (name,))
        self._publish_state()
        return True

    def list_workflows(self) -> List[Dict]:
        with sqlite3.connect(DB) as c:
            rows = c.execute(
                "SELECT id,name,enabled,last_run,run_count,last_status,spec FROM workflows"
            ).fetchall()
        workflows = []
        for r in rows:
            try:
                spec = json.loads(r[6] or "{}")
            except Exception:
                spec = {}
            steps = spec.get("steps", [])
            workflows.append({
                "id": r[0],
                "name": r[1],
                "enabled": bool(r[2]),
                "last_run": r[3],
                "run_count": r[4],
                "last_status": r[5],
                "description": spec.get("description", ""),
                "step_count": len(steps),
                "actions": [s.get("action", "") for s in steps],
            })
        return workflows

    def get_workflow(self, name: str) -> Optional[dict]:
        with sqlite3.connect(DB) as c:
            row = c.execute("SELECT spec FROM workflows WHERE name=?", (name,)).fetchone()
        return json.loads(row[0]) if row else None

    def enable_workflow(self, name: str, enabled: bool = True):
        with sqlite3.connect(DB) as c:
            c.execute("UPDATE workflows SET enabled=? WHERE name=?", (int(enabled), name))
        self._publish_state()

    # ── Execution ──────────────────────────────────────────────────────────────
    async def run(self, name: str, initial_vars: dict = None) -> Dict:
        spec = self.get_workflow(name)
        if not spec:
            return {"error": f"Workflow '{name}' not found"}

        if self._running.get(name):
            return {"error": f"Workflow '{name}' already running"}

        self._running[name] = True
        self._publish_state()
        self._publish_event("workflow.started", {"workflow": name})
        started = datetime.now().isoformat()
        ctx = {
            "orchestrator": self.orchestrator,
            "variables":    initial_vars or {},
            "workflow":     name,
        }

        step_results = []
        status       = "success"
        log_lines    = []

        try:
            steps = spec.get("steps", [])
            for i, step in enumerate(steps):
                action = step.get("action", "")
                log_lines.append(f"Step {i+1}/{len(steps)}: {action}")
                result = await _execute_step(step, ctx)
                ctx["last_result"] = result
                step_results.append({"step": i+1, "action": action, "result": result})
                self._publish_event(
                    "workflow.step",
                    {"workflow": name, "step": i + 1, "total": len(steps), "action": action, "result": result},
                )
                log_lines.append(f"  → {json.dumps(result)[:200]}")

                if "error" in result and step.get("stop_on_error", True):
                    status = "failed"
                    break

                # Condition branch: skip remaining if false
                if action == "condition_branch" and not result.get("result", True):
                    if step.get("stop_if_false", False):
                        log_lines.append("  Condition false, stopping workflow.")
                        break
        except Exception as e:
            status = "error"
            log_lines.append(f"EXCEPTION: {e}")
        finally:
            self._running[name] = False

        finished = datetime.now().isoformat()
        log_text = "\n".join(log_lines)

        # Update DB
        with sqlite3.connect(DB) as c:
            wf = c.execute("SELECT id FROM workflows WHERE name=?", (name,)).fetchone()
            if wf:
                c.execute(
                    "UPDATE workflows SET last_run=?, run_count=run_count+1, last_status=? WHERE id=?",
                    (finished, status, wf[0])
                )
                c.execute(
                    "INSERT INTO runs (workflow_id, started, finished, status, log) VALUES (?,?,?,?,?)",
                    (wf[0], started, finished, status, log_text)
                )

        logger.info(f"[Workflow] '{name}' finished: {status}")
        payload = {
            "workflow": name,
            "status":   status,
            "steps":    len(steps),
            "results":  step_results,
            "started":  started,
            "finished": finished,
        }
        self._publish_state()
        self._publish_event("workflow.finished", payload)
        return payload

    async def run_spec(self, spec: dict, save: bool = False) -> Dict:
        """Run a workflow from a spec dict directly (optionally saving it)."""
        if save:
            self.save_workflow(spec)
        name = spec.get("name", f"adhoc_{int(time.time())}")
        # Temporarily register
        original = self.get_workflow(name)
        self.save_workflow(spec)
        result = await self.run(name)
        if not save and not original:
            self.delete_workflow(name)
        return result

    # ── AI Workflow Generation ─────────────────────────────────────────────────
    async def generate_workflow_from_description(
        self, description: str, orchestrator=None
    ) -> Dict:
        """
        Ask LLM to generate a workflow spec from a natural language description.
        """
        orc = orchestrator or self.orchestrator
        if not orc:
            return {"error": "No orchestrator for workflow generation"}

        prompt = f"""Generate a JARVIS workflow JSON for: "{description}"

Available actions: log, notify, run_command, open_app, llm_query, file_operation, http_request, wait, set_variable, condition_branch

Return ONLY valid JSON:
{{
  "name": "snake_case_name",
  "description": "{description}",
  "steps": [
    {{"action": "log", "params": {{"message": "Starting"}}}},
    ...
  ]
}}"""

        resp = await orc.process(prompt, context={"mode": "json_generation"})
        raw  = resp.get("message", "{}")
        try:
            # Extract JSON from response
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                spec = json.loads(match.group())
                return {"spec": spec, "generated": True}
        except Exception as e:
            return {"error": f"Parse failed: {e}", "raw": raw[:300]}
        return {"error": "No JSON found in LLM response", "raw": raw[:300]}

    # ── Scheduled Execution ───────────────────────────────────────────────────
    def schedule(self, name: str, cron_seconds: int, loop: asyncio.AbstractEventLoop = None):
        """Run a workflow repeatedly every N seconds in background."""
        def _bg():
            while True:
                time.sleep(cron_seconds)
                spec = self.get_workflow(name)
                if spec:
                    lp = loop or asyncio.new_event_loop()
                    lp.run_until_complete(self.run(name))

        t = threading.Thread(target=_bg, daemon=True)
        t.start()
        logger.info(f"[Workflow] Scheduled '{name}' every {cron_seconds}s")

    def get_run_history(self, workflow_name: str, limit: int = 20) -> List[Dict]:
        with sqlite3.connect(DB) as c:
            wf = c.execute("SELECT id FROM workflows WHERE name=?", (workflow_name,)).fetchone()
            if not wf:
                return []
            rows = c.execute(
                "SELECT started,finished,status,log FROM runs "
                "WHERE workflow_id=? ORDER BY id DESC LIMIT ?",
                (wf[0], limit)
            ).fetchall()
        return [{"started":r[0],"finished":r[1],"status":r[2],"log":r[3][:500]} for r in rows]

    # ── Built-in Workflows ─────────────────────────────────────────────────────
    def install_default_workflows(self):
        """Install useful built-in workflows."""
        defaults = [
            {
                "name": "morning_startup",
                "description": "Open work apps and greet user each morning",
                "steps": [
                    {"action": "notify",    "params": {"message": "Good morning! JARVIS online."}},
                    {"action": "log",       "params": {"message": "Morning startup triggered"}},
                    {"action": "llm_query", "params": {"prompt": "Give me a 1-sentence motivational message for the morning."}},
                ]
            },
            {
                "name": "system_cleanup",
                "description": "Clean temp files and optimize system",
                "steps": [
                    {"action": "log",         "params": {"message": "Starting system cleanup"}},
                    {"action": "run_command", "params": {"command": "del /q /f %temp%\\* 2>nul"}},
                    {"action": "notify",      "params": {"message": "System cleanup complete!"}},
                ]
            },
            {
                "name": "ai_research_pipeline",
                "description": "Research a topic and summarize findings",
                "steps": [
                    {"action": "log",       "params": {"message": "Starting AI research pipeline"}},
                    {"action": "llm_query", "params": {"prompt": "{{variables.topic}} — provide a comprehensive research summary in bullet points."}},
                    {"action": "file_operation", "params": {"op": "write", "path": "research_output.txt", "content": "{{result}}"}},
                    {"action": "notify",    "params": {"message": "Research complete! Check research_output.txt"}},
                ]
            },
        ]
        for wf in defaults:
            self.save_workflow(wf)
        logger.info(f"[Workflow] Installed {len(defaults)} default workflows")
        self._publish_state()
        return len(defaults)

    def running_workflows(self) -> List[str]:
        return [name for name, running in self._running.items() if running]

    def _publish_state(self) -> None:
        if not getattr(self, "bus", None):
            return
        self.bus.set_state("workflows", self.list_workflows(), source="workflow_engine")
        self.bus.set_state("running_workflows", self.running_workflows(), source="workflow_engine")

    def _publish_event(self, topic: str, payload: dict) -> None:
        if getattr(self, "bus", None):
            self.bus.publish(topic, payload, source="workflow_engine")
