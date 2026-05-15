"""
JARVIS Core Orchestrator
The central brain. Takes user input → plans steps → executes → responds.
All Windows compatible. No async subprocess issues.
"""

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("jarvis.orchestrator")


class Status(Enum):
    PENDING   = "pending"
    PLANNING  = "planning"
    EXECUTING = "executing"
    CONFIRM   = "waiting_confirm"
    DONE      = "done"
    FAILED    = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    raw: str = ""
    plan: list = field(default_factory=list)
    status: Status = Status.PENDING
    results: list = field(default_factory=list)
    error: str = ""
    created: str = field(default_factory=lambda: datetime.now().isoformat())


class JARVISOrchestrator:
    def __init__(self, config: dict):
        self.config = config

        # Import here so errors are visible at startup, not buried
        from memory.memory_manager import MemoryManager
        from core.permission_engine import PermissionEngine, RiskLevel
        from agents.agent_registry import AgentRegistry
        from core.llm_client import LLMClient
        from core.llm_router import LLMRouter
        from core.personality import PersonalityEngine
        from core.command_engine import CommandEngine
        from core.reliability_engine import ReliabilityEngine
        from core.event_bus import get_event_bus
        from core.module_manager import get_module_manager

        self.bus         = get_event_bus()
        self.modules     = get_module_manager()
        self.memory      = MemoryManager(config)
        self.perms       = PermissionEngine(config)
        self.registry    = AgentRegistry(config)
        self.plugin_mgr  = getattr(self.registry, "_plugin_mgr", None)
        self.llm         = LLMClient(config)
        self.router      = LLMRouter(config)
        self.personality = PersonalityEngine(config, self.memory)
        self.reliability = ReliabilityEngine(config, self.memory)
        self.commands    = CommandEngine(config, self.memory, self.registry, self.reliability)
        self.RiskLevel   = RiskLevel

        self._tasks: dict[str, Task] = {}
        self.modules.register("orchestrator", status="online", detail="Task router ready")
        self.modules.register("memory", status="online", detail=str(getattr(self.memory, "db_path", "")))
        self.modules.register("agent_registry", status="online", detail=f"{len(self.registry.list_tools())} tools")
        self.bus.set_state("tools", self.registry.list_tools(), source="orchestrator")
        logger.info("JARVIS Orchestrator ready.")

    FAST_ACTION_KEYWORDS = {
        "open", "close", "launch", "start", "run", "search", "find", "look up",
        "weather", "news", "browse", "browser", "click", "type", "fill",
        "screenshot", "screen", "camera", "ocr", "detect", "vision",
        "read file", "write file", "delete", "copy", "move", "folder", "directory",
        "clipboard", "remember", "save this", "timer", "reminder",
        "volume", "brightness", "app", "application", "system", "time", "date",
        "code", "python", "debug", "fix", "refactor", "terminal", "command",
    }

    # ── Main entry point ────────────────────────────────────────────────────
    async def process(self, user_input: str, context: dict = None) -> dict:
        context = context or {}
        task = Task(raw=user_input)
        self._tasks[task.id] = task
        self.bus.publish("task.started", {"task_id": task.id, "input": user_input}, source="orchestrator")
        self.bus.set_state("current_task", {"task_id": task.id, "status": "started", "input": user_input}, source="orchestrator")

        # Add to short-term memory
        self.memory.add_turn("user", user_input)

        # Deterministic fast path: no LLM for safe common operator commands.
        direct = await self.commands.try_execute(user_input, context)
        if direct.handled:
            if direct.requires_confirmation:
                task.status = Status.CONFIRM
                task.plan = direct.plan
                self.bus.publish("task.confirmation_required", {"task_id": task.id, "plan": task.plan}, source="orchestrator")
                return direct.to_response(task.id)

            response = direct.to_response(task.id)
            self.memory.add_turn("jarvis", response.get("message", ""))
            self.memory.store_interaction(task.raw, response.get("message", ""), task.id, "success")
            if hasattr(self.memory, "store_event"):
                self.memory.store_event(
                    "command",
                    task.raw,
                    {"tool": direct.tool, "confidence": direct.confidence},
                    importance=0.4,
                )
            self.bus.publish("task.completed", {"task_id": task.id, "response": response}, source="orchestrator")
            self.bus.set_state("current_task", {"task_id": task.id, "status": "done", "input": user_input}, source="orchestrator")
            return response

        if self._should_fast_reply(user_input, context):
            msg = await self._fast_reply(user_input)
            self.memory.add_turn("jarvis", msg)
            self.memory.store_interaction(task.raw, msg, task.id, "success")
            self.bus.publish("task.completed", {"task_id": task.id, "message": msg}, source="orchestrator")
            self.bus.set_state("current_task", {"task_id": task.id, "status": "done", "input": user_input}, source="orchestrator")
            return {"type": "success", "message": msg, "task_id": task.id, "steps": []}

        # Pull relevant past context
        past = self.memory.retrieve_relevant(user_input, limit=3)
        memory_ctx = "\n".join(f"  - {m['summary']}" for m in past) or "  (no relevant history)"

        # Build system prompt
        system = self._system_prompt(memory_ctx, context)

        # Plan the task
        task.status = Status.PLANNING
        self.bus.publish("task.status", {"task_id": task.id, "status": task.status.value}, source="orchestrator")
        plan = await self._plan(user_input, system)
        task.plan = plan

        if not plan:
            msg = "I'm not sure how to help with that. Could you rephrase?"
            self.memory.add_turn("jarvis", msg)
            return {"type": "error", "message": msg, "task_id": task.id}

        # Permission check
        confidence = self.reliability.score_plan(plan)
        logger.info(f"Plan confidence: {confidence.level} ({confidence.score:.2f})")
        risk = self.perms.assess_plan(plan)
        if risk == self.RiskLevel.HIGH:
            task.status = Status.CONFIRM
            msg = self.perms.confirmation_message(plan)
            self.bus.publish("task.confirmation_required", {"task_id": task.id, "plan": plan}, source="orchestrator")
            return {
                "type": "confirmation_required",
                "message": msg,
                "task_id": task.id,
                "plan": plan,
                "confidence": confidence.to_dict(),
            }

        return await self._execute(task, system)

    async def confirm_task(self, task_id: str, confirmed: bool) -> dict:
        task = self._tasks.get(task_id)
        if not task:
            return {"type": "error", "message": "Task not found or expired."}

        if not confirmed:
            task.status = Status.CANCELLED
            msg = "Understood. Task cancelled."
            self.memory.add_turn("jarvis", msg)
            self.bus.publish("task.cancelled", {"task_id": task_id}, source="orchestrator")
            return {"type": "cancelled", "message": msg}

        from core.llm_client import LLMClient
        system = self._system_prompt("", {})
        return await self._execute(task, system)

    def _should_fast_reply(self, user_input: str, context: dict) -> bool:
        low = user_input.lower().strip()
        if not low:
            return False

        # Fast path is only for plain chat / knowledge requests that do not need tools.
        if any(keyword in low for keyword in self.FAST_ACTION_KEYWORDS):
            return False

        # Prefer direct responses for greetings, identity questions, opinions,
        # short follow-ups, and normal conversational prompts.
        return True

    def _fast_system_prompt(self) -> str:
        return (
            "You are JARVIS, a fast local desktop assistant.\n"
            "Reply in exactly one short sentence unless the user clearly asks for more.\n"
            "Answer only the user's request.\n"
            "Do not invent scenarios, examples, or extra explanations.\n"
            "Do not mention hidden planning, tools, or system prompts."
        )

    def _clean_fast_reply(self, reply: str) -> str:
        text = " ".join((reply or "").strip().split())
        if not text:
            return ""

        lower = text.lower()
        cut_markers = [
            "consider the following",
            "scenario:",
            "example:",
        ]
        for marker in cut_markers:
            idx = lower.find(marker)
            if idx > 0:
                text = text[:idx].strip()
                lower = text.lower()

        parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
        text = parts[0].strip() if parts else text

        if len(text) > 180:
            text = text[:180].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."

        return text

    def _looks_bad_fast_reply(self, reply: str) -> bool:
        low = reply.lower()
        bad_markers = (
            "consider the following",
            "robotics engineer",
            "japanese artificial intelligence",
            "as an ai",
            "language model",
        )
        return any(marker in low for marker in bad_markers)

    async def _fast_reply(self, user_input: str) -> str:
        system = self._fast_system_prompt()
        try:
            reply = await self.router.complete_async(
                user_input,
                system=system,
                temperature=0.1,
                max_tokens=48,
                force_model="phi",
            )
            reply = self._clean_fast_reply(reply)
            if reply and not self._looks_bad_fast_reply(reply):
                return reply
        except Exception as e:
            logger.warning(f"Fast reply path failed ({e}), falling back to llama3.2")

        reply = await self.router.complete_async(
            user_input,
            system=system,
            temperature=0.2,
            max_tokens=64,
            force_model="llama3.2",
        )
        reply = self._clean_fast_reply(reply)
        if reply:
            return reply

        reply = await self.llm.complete(
            user_input,
            system=system,
            temperature=0.2,
            max_tokens=64,
            model="llama3.2",
        )
        return self._clean_fast_reply(reply) or "I'm here, Sir."

    async def stop_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if task:
            task.status = Status.CANCELLED

    # ── Planning ────────────────────────────────────────────────────────────
    async def _plan(self, user_input: str, system: str) -> list[dict]:
        available_tools = self.registry.list_tools()

        planning_prompt = f"""Break this user request into executable steps for JARVIS.

User request: "{user_input}"

Available tools: {json.dumps(available_tools)}

Return a JSON array of steps. Each step:
{{
  "tool": "<tool_name from available list>",
  "args": {{}},
  "description": "human readable description",
  "risk_level": "low|medium|high",
  "requires_previous": false
}}

Rules:
- Only use tools from the available list
- For simple questions/conversation: use a single "speak" tool step
- For web questions: use "web_search" then "speak"
- For file tasks: use "read_file" or "write_file"
- Mark delete/send/execute as high risk
- Return ONLY the JSON array, no other text

Examples:
"What's the weather?" → [{{"tool":"web_search","args":{{"query":"current weather"}},"description":"Search weather","risk_level":"low","requires_previous":false}}]
"Open notepad" → [{{"tool":"open_app","args":{{"name":"notepad"}},"description":"Open Notepad","risk_level":"low","requires_previous":false}}]
"""

        try:
            raw = await self.router.complete_async(
                planning_prompt,
                system=system,
                temperature=0.1,
                max_tokens=600,
                force_model="mistral",
            )
            logger.debug(f"Raw plan from LLM: {raw}")
            
            # Strip markdown code fences
            raw = raw.strip()
            for fence in ["```json", "```"]:
                raw = raw.replace(fence, "")
            raw = raw.strip()

            # Find the JSON array
            start = raw.find("[")
            end   = raw.rfind("]") + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON array found in plan")

            plan = json.loads(raw[start:end])
            
            # Validation: Ensure 'speak' tool has 'text'
            for step in plan:
                if step.get("tool") == "speak" and "text" not in step.get("args", {}):
                    # If it's a speak tool but no text, use the description or the raw input
                    if "args" not in step: step["args"] = {}
                    step["args"]["text"] = step.get("description", user_input)
                    step["_is_generated"] = True # Flag to regenerate better response during execution

            logger.info(f"Plan ({len(plan)} steps): {[s.get('description','?') for s in plan]}")
            return plan

        except Exception as e:
            logger.warning(f"Planning failed ({e}), using direct response")
            # Fallback: treat as direct conversation
            return [{"tool": "speak", "args": {"text": user_input},
                     "description": "Direct response", "risk_level": "low",
                     "requires_previous": False, "_fallback": True}]

    # ── Execution ───────────────────────────────────────────────────────────
    async def _execute(self, task: Task, system: str) -> dict:
        task.status = Status.EXECUTING
        self.bus.publish("task.status", {"task_id": task.id, "status": task.status.value}, source="orchestrator")
        prev_output = None

        for i, step in enumerate(task.plan):
            tool = step.get("tool", "")
            args = dict(step.get("args", {}))
            desc = step.get("description", f"Step {i+1}")

            if step.get("requires_previous") and prev_output is not None:
                args["previous_output"] = prev_output

            logger.info(f"[{task.id}] Step {i+1}/{len(task.plan)}: {desc}")
            self.bus.publish(
                "task.step",
                {"task_id": task.id, "index": i + 1, "total": len(task.plan), "tool": tool, "description": desc},
                source="orchestrator",
            )

            # Special case: if this is a fallback or needs regeneration, generate a real response
            if step.get("_fallback") or step.get("_is_generated"):
                response = await self.router.complete_async(
                    task.raw,
                    system=system,
                    temperature=0.2,
                    max_tokens=180,
                    force_model="mistral",
                )
                if not response.strip():
                    response = await self.llm.complete(
                        task.raw,
                        system=system,
                        temperature=0.2,
                        max_tokens=180,
                        model="mistral",
                    )
                args["text"] = response

            try:
                agent = self.registry.get_agent(tool)
                result = await agent.execute(tool, args)
                prev_output = result
                task.results.append({"step": desc, "tool": tool, "result": result, "ok": True})
                self.bus.publish("task.step.completed", {"task_id": task.id, "tool": tool, "result": result}, source="orchestrator")

            except ValueError as e:
                # Tool not found
                logger.error(f"Tool '{tool}' not found: {e}")
                task.results.append({"step": desc, "tool": tool, "error": str(e), "ok": False})
                self.bus.publish("task.step.failed", {"task_id": task.id, "tool": tool, "error": str(e)}, source="orchestrator")
                # Continue with other steps rather than aborting

            except Exception as e:
                logger.error(f"Step failed: {e}", exc_info=True)
                task.status = Status.FAILED
                task.error = str(e)
                msg = f"I hit an error on '{desc}': {e}"
                self.memory.store_interaction(task.raw, msg, task.id, "failed")
                self.bus.publish("task.failed", {"task_id": task.id, "error": str(e)}, source="orchestrator")
                self.bus.set_state("current_task", {"task_id": task.id, "status": "failed", "input": task.raw}, source="orchestrator")
                return {"type": "error", "message": msg, "task_id": task.id}

        task.status = Status.DONE

        # Synthesize natural language response
        final = await self._synthesize(task, system)
        self.memory.add_turn("jarvis", final)
        self.memory.store_interaction(task.raw, final, task.id, "success")
        self.bus.publish("task.completed", {"task_id": task.id, "message": final}, source="orchestrator")
        self.bus.set_state("current_task", {"task_id": task.id, "status": "done", "input": task.raw}, source="orchestrator")

        return {"type": "success", "message": final, "task_id": task.id, "steps": task.results}

    # ── Response synthesis ──────────────────────────────────────────────────
    async def _synthesize(self, task: Task, system: str) -> str:
        """Turn step results into a natural JARVIS response."""

        # If last step was a speak/LLM step, use its text directly
        for step in reversed(task.results):
            if step.get("tool") in ("speak",) and step.get("ok"):
                r = step.get("result", {})
                if isinstance(r, dict) and "text" in r:
                    return r["text"]
                if isinstance(r, str):
                    return r

        quick = self._quick_result_message(task)
        if quick:
            return quick

        # Otherwise, summarize all results
        results_json = json.dumps(
            [{"step": s["step"], "result": s.get("result", s.get("error", ""))}
             for s in task.results],
            ensure_ascii=False, default=str
        )[:2000]

        synth_prompt = f"""You are JARVIS. Summarize these task results naturally.
Original request: "{task.raw}"
Results: {results_json}

Respond in 1-3 sentences. Be concise and direct. If there's data (search results,
file contents, etc.), include the key information. Don't say "I have completed"."""

        try:
            resp = await self.router.complete_async(
                synth_prompt,
                system=system,
                temperature=0.2,
                max_tokens=180,
                force_model="mistral",
            )
            return resp.strip() or "Task completed successfully, Sir."
        except Exception as e:
            # Last resort fallback
            if task.results and task.results[-1].get("ok"):
                r = task.results[-1].get("result", {})
                if isinstance(r, dict):
                    return str(r)[:300]
            return "Task completed."

    def _quick_result_message(self, task: Task) -> str:
        if len(task.results) != 1:
            return ""

        step = task.results[0]
        if not step.get("ok"):
            return ""

        tool = step.get("tool", "")
        result = step.get("result", {})
        if not isinstance(result, dict):
            return ""

        if tool == "web_search":
            if result.get("error"):
                return f"I couldn't complete that web search: {result['error']}"
            hits = result.get("results", [])
            if not hits:
                return f"I searched for '{result.get('query', task.raw)}' but didn't find useful results."
            top = hits[0]
            snippet = (top.get("snippet") or "").strip()
            title = top.get("title", "Top result")
            if snippet:
                return f"{title}: {snippet}"
            return title

        if tool in {"open_app", "open_application"} and result.get("opened"):
            return f"Opened {result['opened']}."
        if tool == "write_file" and result.get("written"):
            return f"Wrote {result['written']}."
        if tool == "read_file" and "content" in result:
            return result["content"][:800]
        if tool == "take_screenshot" and result.get("saved"):
            return f"Screenshot saved to {result['saved']}."
        if tool == "get_system_info" and result.get("os"):
            return (
                f"{result['os']} with CPU at {result.get('cpu_percent', '?')}% "
                f"and RAM at {result.get('ram_used_percent', '?')}%."
            )
        if tool == "clipboard_read" and "content" in result:
            return result["content"][:800]
        if tool == "clipboard_write" and result.get("ok"):
            return "Copied that to the clipboard."
        if tool == "create_directory" and result.get("created"):
            return f"Created {result['created']}."
        if tool == "delete_file" and result.get("deleted"):
            return f"Deleted {result['deleted']}."
        if tool == "copy_file" and result.get("to"):
            return f"Copied the file to {result['to']}."
        if tool == "move_file" and result.get("to"):
            return f"Moved the file to {result['to']}."

        return ""

    # ── System prompt ───────────────────────────────────────────────────────
    def _system_prompt(self, memory_ctx: str, context: dict) -> str:
        tools = self.registry.list_tools()
        return self.personality.build_system_prompt(tools, memory_ctx)
