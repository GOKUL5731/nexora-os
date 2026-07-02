from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable

from ..core.event_bus import EventBus
from ..memory.engine import MemoryEngine

log = logging.getLogger("nexora.agents")


@dataclass(slots=True)
class AgentHealth:
    name: str
    status: str = "idle"
    queued: int = 0
    completed: int = 0
    failed: int = 0
    last_error: str = ""
    last_run_at: float = 0.0


class BaseAgent:
    def __init__(self, name: str, bus: EventBus, memory: MemoryEngine, heartbeat_interval: int = 30, task_timeout: int = 60) -> None:
        self.name = name
        self.bus = bus
        self.memory = memory
        self.queue: asyncio.Queue[tuple[str, dict[str, Any], asyncio.Future]] = asyncio.Queue()
        self.health = AgentHealth(name)
        self._worker: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._heartbeat_interval = heartbeat_interval
        self._task_timeout = task_timeout

    def start(self) -> None:
        if not self._worker or self._worker.done():
            self._worker = asyncio.create_task(self._run(), name=f"agent:{self.name}")
        if not self._heartbeat_task or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name=f"heartbeat:{self.name}")

    async def stop(self) -> None:
        if self._worker and not self._worker.done():
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        self.health.status = "stopped"

    async def _heartbeat_loop(self) -> None:
        """Publish periodic heartbeat events for monitoring"""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            self.bus.publish(
                "agent.heartbeat",
                {
                    "agent": self.name,
                    "status": self.health.status,
                    "queued": self.health.queued,
                    "completed": self.health.completed,
                    "failed": self.health.failed,
                    "last_error": self.health.last_error,
                    "last_run_at": self.health.last_run_at,
                    "timestamp": time.time()
                },
                self.name
            )

    async def submit(self, task: dict[str, Any]) -> dict[str, Any]:
        self.start()
        task_id = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        await self.queue.put((task_id, task, future))
        self.health.queued = self.queue.qsize()
        self.bus.publish("agent.queued", {"agent": self.name, "task_id": task_id}, self.name)
        return await future

    async def _run(self) -> None:
        while True:
            task_id, task, future = await self.queue.get()
            self.health.queued = self.queue.qsize()
            self.health.status = "running"
            self.health.last_run_at = time.time()
            self.bus.publish("agent.started", {"agent": self.name, "task_id": task_id}, self.name)
            try:
                context = self.memory.search(str(task), 5)
                # Execute task with timeout
                result = await asyncio.wait_for(
                    self.execute(task, context),
                    timeout=self._task_timeout
                )
                self.health.completed += 1
                future.set_result({"task_id": task_id, "agent": self.name, **result})
                self.bus.publish("agent.completed", {"agent": self.name, "task_id": task_id}, self.name)
            except asyncio.TimeoutError:
                log.warning("%s task %s timed out after %d seconds", self.name, task_id, self._task_timeout)
                self.health.failed += 1
                self.health.last_error = f"Task timed out after {self._task_timeout} seconds"
                future.set_result({
                    "task_id": task_id,
                    "agent": self.name,
                    "ok": False,
                    "error": f"Task timed out after {self._task_timeout} seconds"
                })
                self.bus.publish(
                    "agent.failed",
                    {"agent": self.name, "task_id": task_id, "error": f"Task timed out after {self._task_timeout} seconds"},
                    self.name
                )
            except Exception as exc:
                log.exception("%s failed", self.name)
                self.health.failed += 1
                self.health.last_error = str(exc)
                future.set_result({"task_id": task_id, "agent": self.name, "ok": False, "error": str(exc)})
                self.bus.publish("agent.failed", {"agent": self.name, "task_id": task_id, "error": str(exc)}, self.name)
            finally:
                self.health.status = "idle"
                self.queue.task_done()

    async def execute(self, task: dict[str, Any], context: list[dict[str, Any]]) -> dict[str, Any]:
        return {"ok": True, "message": f"{self.name} accepted the task.", "context_count": len(context)}


class AutonomousAgent(BaseAgent):
    """
    Fully autonomous agent using a ReAct (Reasoning + Acting) loop.
    It thinks, picks a tool, executes it, observes the result,
    and loops until the task is complete or it hits the step limit.
    Errors are automatically fed back to the LLM for self-correction.
    """

    SYSTEM_PROMPT = """You are NEXORA, a fully autonomous AI agent. You can accomplish any task by reasoning step-by-step and using tools.

You MUST respond with a JSON object only. No extra text outside the JSON.

Available tools:
- run_command   : Run a shell/PowerShell command. params: {"command": "<cmd>"}
- read_file     : Read a file. params: {"path": "<absolute_path>"}
- write_file    : Write/create a file. params: {"path": "<absolute_path>", "content": "<text>"}
- launch_app    : Open any application by name. params: {"app_name": "<name>"}
- open_url      : Open a URL in the browser. params: {"url": "<url>"}
- search_web    : Search the internet. params: {"query": "<q>"}
- ask_user      : Ask the user a question when stuck. params: {"question": "<q>"}
- complete      : Task is fully done. params: {"result": "<final answer or summary>"}

Response format:
{
  "thought": "<your reasoning about what to do next>",
  "action": "<tool_name>",
  "params": { ... }
}

Rules:
- Always think before acting.
- If a command fails, read the error, adjust, and try a different approach.
- Never give up without at least 3 retries with different approaches.
- Use 'complete' only when the task is truly finished.
- Keep thoughts concise (1-2 sentences).
"""

    MAX_STEPS = 15

    async def execute(self, task: dict[str, Any], context: list[dict[str, Any]]) -> dict[str, Any]:
        from ..core.llm import OllamaClient
        import json as _json
        import re as _re

        llm = OllamaClient()
        if not llm.ready():
            # Fallback: produce a structured plan without execution
            return await self._fallback_plan(task, context)

        goal = str(task.get("goal") or task.get("input") or task.get("message") or "").strip()
        if not goal:
            return {"ok": False, "message": "No goal provided to the autonomous agent."}

        history: list[str] = []
        steps_log: list[dict[str, Any]] = []

        for step in range(1, self.MAX_STEPS + 1):
            # Build the current prompt with goal + all history
            history_text = "\n".join(history) if history else "No actions taken yet."
            prompt = (
                f"Goal: {goal}\n\n"
                f"Action history:\n{history_text}\n\n"
                f"What do you do next? Respond with JSON only."
            )

            llm_result = await asyncio.to_thread(
                llm.generate, prompt, self.SYSTEM_PROMPT, True
            )

            if not llm_result.get("ok"):
                return {"ok": False, "message": f"LLM error: {llm_result.get('message')}"}

            raw = llm_result.get("message", "")

            # Parse JSON from the LLM response
            action_data = None
            try:
                # Find JSON block even if there is surrounding text
                json_match = _re.search(r'\{.*\}', raw, _re.DOTALL)
                if json_match:
                    action_data = _json.loads(json_match.group())
            except Exception:
                pass

            if not action_data or "action" not in action_data:
                history.append(f"Step {step}: LLM returned malformed JSON, retrying...\nRaw: {raw[:200]}")
                continue

            thought = action_data.get("thought", "")
            action = action_data.get("action", "")
            params = action_data.get("params", {})

            self.bus.publish("agent.step", {
                "agent": self.name, "step": step, "thought": thought,
                "action": action, "params": params
            }, self.name)

            step_entry: dict[str, Any] = {"step": step, "thought": thought, "action": action, "params": params}

            # ── Execute the chosen tool ──────────────────────────────────────
            if action == "complete":
                result_text = params.get("result", "Task completed.")
                steps_log.append({**step_entry, "result": result_text})
                self.memory.store(goal, "episodic", ["autonomous", "goal"])
                self.memory.store(result_text, "semantic", ["autonomous", "result"])
                return {
                    "ok": True,
                    "message": result_text,
                    "steps": steps_log,
                    "total_steps": step,
                }

            observation = await self._execute_tool(action, params)
            step_entry["result"] = observation
            steps_log.append(step_entry)

            obs_text = _json.dumps(observation) if isinstance(observation, dict) else str(observation)
            history.append(
                f"Step {step}:\n  Thought: {thought}\n  Action: {action}\n  Params: {_json.dumps(params)}\n  Observation: {obs_text}"
            )

        return {
            "ok": True,
            "message": f"Reached the maximum of {self.MAX_STEPS} steps. Here is what was accomplished so far.",
            "steps": steps_log,
            "total_steps": self.MAX_STEPS,
        }

    async def _execute_tool(self, action: str, params: dict[str, Any]) -> Any:
        """Execute a named tool and return its observation."""
        import subprocess as _sp
        import os as _os

        try:
            if action == "run_command":
                cmd = params.get("command", "")
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=_sp.PIPE, stderr=_sp.PIPE
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
                out = stdout.decode("utf-8", errors="replace")
                err = stderr.decode("utf-8", errors="replace")
                if proc.returncode == 0:
                    return {"ok": True, "output": out or "(no output)"}
                else:
                    return {"ok": False, "error": err or out or f"Exit code {proc.returncode}"}

            elif action == "read_file":
                path = params.get("path", "")
                if not _os.path.exists(path):
                    return {"ok": False, "error": f"File not found: {path}"}
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                return {"ok": True, "content": content[:8000]}  # limit to 8k chars

            elif action == "write_file":
                path = params.get("path", "")
                content = params.get("content", "")
                _os.makedirs(_os.path.dirname(_os.path.abspath(path)), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"ok": True, "message": f"Written {len(content)} chars to {path}"}

            elif action == "launch_app":
                app_name = params.get("app_name", "")
                import subprocess
                subprocess.Popen(f'start "" "{app_name}"', shell=True)
                return {"ok": True, "message": f"Launched {app_name}"}

            elif action == "open_url":
                import webbrowser
                url = params.get("url", "")
                webbrowser.open(url)
                return {"ok": True, "message": f"Opened {url}"}

            elif action == "search_web":
                import webbrowser
                query = params.get("query", "")
                url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                webbrowser.open(url)
                return {"ok": True, "message": f"Searched for: {query}"}

            elif action == "ask_user":
                question = params.get("question", "I need more information.")
                # Publish event so the frontend can show this question to user
                self.bus.publish("agent.ask_user", {"question": question}, self.name)
                return {"ok": True, "message": f"Question sent to user: {question}"}

            else:
                return {"ok": False, "error": f"Unknown tool: {action}"}

        except asyncio.TimeoutError:
            return {"ok": False, "error": "Tool execution timed out after 30 seconds."}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _fallback_plan(self, task: dict[str, Any], context: list[dict[str, Any]]) -> dict[str, Any]:
        """Return a structured plan when the LLM is offline."""
        goal = str(task.get("goal") or task.get("input") or "Unnamed goal").strip()
        steps = [
            {"id": 1, "action": "analyze", "description": f"Analyze goal: {goal}"},
            {"id": 2, "action": "research", "description": "Search memory for relevant context"},
            {"id": 3, "action": "execute", "description": "Execute the required operations"},
            {"id": 4, "action": "verify", "description": "Verify and report the result"},
        ]
        return {
            "ok": True,
            "message": f"Plan ready for: {goal}. Note: LLM is offline, so this is a static plan. Start Ollama to enable autonomous execution.",
            "plan": steps,
            "context_count": len(context),
            "autonomous": False,
        }


# ResearchAgent and CodingAgent are not registered in AgentRuntime
# per recovery requirements to reduce agent count to 4.
# These can be re-enabled if research/coding functionality is needed.



class DelegateAgent(BaseAgent):
    def __init__(
        self,
        name: str,
        bus: EventBus,
        memory: MemoryEngine,
        handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> None:
        super().__init__(name, bus, memory)
        self.handler = handler

    async def execute(self, task: dict[str, Any], context: list[dict[str, Any]]) -> dict[str, Any]:
        return await self.handler(task)


class AgentRuntime:
    def __init__(
        self,
        bus: EventBus,
        memory: MemoryEngine,
        voice_handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        vision_handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        workflow_handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        recovery_enabled: bool = True,
        max_failures: int = 3,
    ) -> None:
        self.bus = bus
        self.memory = memory
        self.agents: dict[str, BaseAgent] = {
            "PlannerAgent": AutonomousAgent("AutonomousAgent", bus, memory, task_timeout=300),
            "AutonomousAgent": AutonomousAgent("AutonomousAgent", bus, memory, task_timeout=300),
            "VoiceAgent": DelegateAgent("VoiceAgent", bus, memory, voice_handler),
            "VisionAgent": DelegateAgent("VisionAgent", bus, memory, vision_handler),
            "WorkflowAgent": DelegateAgent("WorkflowAgent", bus, memory, workflow_handler),
        }
        # Note: ResearchAgent and CodingAgent are defined but not registered to reduce agent count as per recovery requirements
        
        # Recovery settings
        self._recovery_enabled = recovery_enabled
        self._max_failures = max_failures
        self._failure_counts = {name: 0 for name in self.agents}
        self._monitor_task: asyncio.Task | None = None

    async def submit(self, agent: str, task: dict[str, Any]) -> dict[str, Any]:
        if agent not in self.agents:
            return {"ok": False, "error": f"Unknown agent: {agent}"}
        result = await self.agents[agent].submit(task)
        self.sync()
        return result

    def health(self) -> list[dict[str, Any]]:
        return [asdict(agent.health) for agent in self.agents.values()]

    def sync(self) -> None:
        self.bus.set_state("agents", {"tool_agents": self.health(), "runtime_agents": self.health()}, "agent_runtime")
        # Start monitor task if not already running
        if self._recovery_enabled and (not self._monitor_task or self._monitor_task.done()):
            self._monitor_task = asyncio.create_task(self._monitor_agents(), name="agent_monitor")

    async def _monitor_agents(self) -> None:
        """Monitor agent health and recover failed agents"""
        while True:
            await asyncio.sleep(10)  # Check every 10 seconds
            for name, agent in self.agents.items():
                if agent.health.failed >= self._max_failures:
                    self._failure_counts[name] += 1
                    log.warning("Agent %s has %d failures, attempting recovery", name, agent.health.failed)
                    if self._recovery_enabled:
                        await self._recover_agent(name)

    async def _recover_agent(self, name: str) -> None:
        """Attempt to recover a failed agent"""
        if name not in self.agents:
            return
        
        agent = self.agents[name]
        log.info("Recovering agent %s", name)
        
        # Stop the agent
        await agent.stop()
        
        # Reset failure count
        agent.health.failed = 0
        agent.health.last_error = ""
        
        # Wait a moment before restarting
        await asyncio.sleep(1)
        
        # Restart the agent
        agent.start()
        
        # Publish recovery event
        self.bus.publish("agent.recovered", {"agent": name}, "agent_runtime")
        log.info("Agent %s recovered successfully", name)

    async def shutdown(self) -> None:
        # Stop monitor task
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # Stop all agents
        await asyncio.gather(*(agent.stop() for agent in self.agents.values()), return_exceptions=True)
        self.sync()
