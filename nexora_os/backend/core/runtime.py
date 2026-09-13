from __future__ import annotations

import asyncio
import logging
import re
import time
import os
from pathlib import Path
from typing import Any

from ..agents.runtime import AgentRuntime
from ..ai_lab.agent_creator import AgentCreator
from ..automation.engine import AutomationEngine
from ..automation.registry import ConnectorRegistry
from ..automation.scheduler import global_scheduler
from ..automation.application_launcher import global_app_launcher
from ..automation.autonomous_executor import global_autonomous_executor
from ..automation.system_control import global_system_control
from ..memory.engine import MemoryEngine
from ..memory.conversation import ConversationMemory
from ..vision.engine import VisionEngine
from ..voice.engine import VoiceEngine
from ..workflows.engine import WorkflowEngine
from ..knowledge import KnowledgeManager
from ..brain import CapabilityRegistry, CognitiveCore, GoalManager
from ..companion import CompanionManager
from ..security import SecurityManager
from ..connectors import ConnectorManager, DesktopConnector, BrowserConnector, TerminalConnector, FilesystemConnector, AndroidConnector, VSCodeConnector
from .event_bus import EventBus
from .cognitive_intelligence import CognitiveIntelligenceEngine
from .human_response import HumanResponseEngine
from .async_runtime import AsyncRuntime
from .health_monitor import HealthMonitor
from .config_manager import ConfigManager
from .scheduler import Scheduler
from .websocket_manager import WebSocketManager
from .error_recovery import ErrorRecoveryManager
from .startup_manager import StartupManager
from .shutdown_manager import ShutdownManager
from ..staging.llm import OllamaClient
from .logger import configure_core_logging
from .module_manager import ModuleManager
from .validation import validate_and_sanitize, ValidationError
from .aliases import expand_command


class NexoraRuntime:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.bus = EventBus()
        self.human_response = HumanResponseEngine()
        self.log = configure_core_logging(root, self.bus)
        self.modules = ModuleManager(self.bus)
        self.async_runtime = AsyncRuntime(self.bus)

        # Core Block 1 Managers
        self.config = ConfigManager(root / "config.json", self.bus)
        self.scheduler = Scheduler(self.bus)
        self.websockets = WebSocketManager(self.bus)
        self.recovery = ErrorRecoveryManager(self.bus, self.modules)
        self.startup_manager = StartupManager(self.bus, self.modules)
        self.shutdown_manager = ShutdownManager(self.bus)

        self.llm = OllamaClient()
        self.goals = GoalManager(root / "databases" / "goals.db")
        self.capabilities = CapabilityRegistry()
        self.memory = MemoryEngine(root / "databases" / "memory.db", self.bus, llm=self.llm)
        self.conversation = ConversationMemory(root / "databases" / "conversation.db", self.bus)
        self.knowledge = KnowledgeManager(root / "databases" / "knowledge.db", self.memory, self.bus, llm=self.llm)
        self.voice = VoiceEngine(self.bus)
        self.vision = VisionEngine(root / "logs" / "captures", self.bus)
        self.cognition = CognitiveIntelligenceEngine(root, self.bus, self.memory, self.knowledge, self.voice, self.vision)
        # connector_manager is registered below; pass it after connectors are wired
        self.automation = AutomationEngine(self.bus, self.vision)
        self.workflows = WorkflowEngine(root / "databases" / "workflows.db", self.bus)
        self.creator = AgentCreator(root / "ai_lab_sandbox", root / "databases" / "generated_agents.json", self.bus, llm=self.llm)
        self.agents = AgentRuntime(
            self.bus,
            self.memory,
            self._voice_task,
            self._vision_task,
            self._workflow_task,
        )
        self.companion = CompanionManager(root / "databases" / "companion.db", self.bus, self.memory)
        self.security = SecurityManager(root / "databases" / "security.db", self.bus)
        self.connector_manager = ConnectorManager()
        self.connector_manager.register("desktop",    DesktopConnector())
        self.connector_manager.register("browser",    BrowserConnector())
        self.connector_manager.register("terminal",   TerminalConnector())
        self.connector_manager.register("filesystem", FilesystemConnector(root_path=str(root)))
        self.connector_manager.register("android",    AndroidConnector())
        self.connector_manager.register("vscode",     VSCodeConnector())
        # Wire connector_manager into AutomationEngine now that all connectors are registered
        self.automation._connectors = self.connector_manager
        # Connector registry — read-only capability manifest
        self.connector_registry = ConnectorRegistry(self.connector_manager)
        self.monitor = HealthMonitor(self.bus, self.modules, self.agents, self.workflows, self.memory, self.async_runtime)
        self.workflows.node_executor = self._execute_node
        self.brain = CognitiveCore(self.bus, self.memory, self.goals, self.capabilities, self._execute_command, self.llm.status, self.knowledge)
        self.task_context: dict[str, Any] = {"recent": [], "last_file_path": ""}
        self._register_capabilities()
        self._register_modules()

        # Voice events
        self.bus.subscribe("voice.utterance", self._on_voice_utterance)
        self.bus.subscribe("voice.activity", self._on_voice_activity)

    async def start(self) -> None:
        await global_scheduler.start()  # Keep for backwards compatibility with automation
        await self.startup_manager.execute_boot_sequence(self)
        if self._config_bool("voice_continuous_listen", False):
            self.voice.start_continuous()
        if self._config_bool("vision_auto_start", False):
            await self.vision.start()
        self.workflows.start()

    async def shutdown(self) -> None:
        self.log.info("NEXORA runtime shutdown requested")
        self.voice.stop_continuous()
        await self.vision.stop()
        await global_scheduler.stop()  # Keep for backwards compatibility
        await self.shutdown_manager.execute_shutdown_sequence(self)
        await self.bus.shutdown()

    async def process(self, text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}

        try:
            # Validate and sanitize input
            text = validate_and_sanitize(text)
        except ValidationError as e:
            self.log.warning("Input validation failed: %s", str(e))
            return {
                "type": "error",
                "message": f"Invalid input: {str(e)}",
                "ok": False
            }

        text = expand_command(text)
        session_id = str(context.get("session_id", "default"))
        language = context.get("language", "en")
        lowered_for_context = text.lower().strip()
        if self._asks_recent_work(lowered_for_context):
            response = self._recent_work_response()
            self.conversation.add_turn(session_id, "user", text, language)
            self.conversation.add_turn(session_id, "assistant", str(response.get("message", "")), language)
            self._remember_task_result(text, response)
            self._schedule_speech(response, context)
            return response
        if self._asks_open_last_file(lowered_for_context):
            self.conversation.add_turn(session_id, "user", text, language)
            response = await self._open_last_file()
            self.conversation.add_turn(session_id, "assistant", str(response.get("message", "")), language)
            self._remember_task_result(text, response)
            self._schedule_speech(response, context)
            return response
        # Record user turn in persistent conversation memory
        self.conversation.add_turn(session_id, "user", text, language)
        # Inject recent conversation context so the brain knows what was said before
        context["conversation_history"] = self.conversation.build_context_string(session_id, n=8)
        context["conversation_messages"] = [
            {"role": turn["role"], "content": turn["content"]}
            for turn in self.conversation.get_recent(session_id, n=8)
            if turn["role"] in {"user", "assistant"}
        ]
        human = self.human_response.respond(text, context, self.knowledge, self.memory)
        if human.handled and not human.background:
            meaningful = self.human_response.meaningful_memory(text)
            if meaningful:
                self.memory.store(meaningful, "preference", ["conversation", "user_context"])
            response = {
                "type": "success",
                "ok": True,
                "message": human.message,
                "intent": human.intent.value,
                "mode": human.mode.value,
                "latency_ms": human.data.get("latency_ms", 0),
                "conversation": self.human_response.snapshot(session_id),
            }
            # Record assistant turn
            self.conversation.add_turn(session_id, "assistant", human.message, language)
            self.bus.publish("runtime.response", response, "human_response")
            self._remember_task_result(text, response)
            self.cognition.self_monitor(text, response, {"session_id": session_id, "mode": response["mode"]})
            self._schedule_speech(response, context)
            return response

        if human.handled and human.background:
            task_name = f"brain.background.{int(time.time() * 1000)}"
            awaitable = self._process_with_brain(text, context, session_id, task_name)
            if self.async_runtime.started:
                self.async_runtime.create_task(task_name, awaitable)
            else:
                asyncio.create_task(awaitable, name=task_name)
            response = {
                "type": "accepted",
                "ok": True,
                "message": human.message,
                "intent": human.intent.value,
                "mode": human.mode.value,
                "background": True,
                "task_id": task_name,
                "latency_ms": human.data.get("latency_ms", 0),
            }
            self.bus.publish("runtime.response", response, "human_response")
            self._remember_task_result(text, response)
            self.cognition.self_monitor(text, response, {"session_id": session_id, "mode": response["mode"]})
            self._schedule_speech(response, context)
            return response

        result = await self._process_with_brain(text, context, session_id)
        self._remember_task_result(text, result)
        self._schedule_speech(result, context)
        return result

    async def _process_with_brain(
        self,
        text: str,
        context: dict[str, Any],
        session_id: str,
        task_name: str | None = None,
    ) -> dict[str, Any]:
        if task_name:
            await asyncio.sleep(0.05)
            self.bus.publish("runtime.progress", {"task_id": task_name, "message": "Understanding the request..."}, "human_response")
        source = str(context.get("mode", "text"))
        language = context.get("language", "en")
        cognitive_context = self.cognition.build_unified_context(text, source, context)
        result = await self.brain.process_request(
            text,
            source=source,
            context={**context, "cognitive": cognitive_context},
            permissions=context.get("permissions", {}) if isinstance(context.get("permissions", {}), dict) else {},
            session_id=session_id,
        )
        result["self_monitor"] = self.cognition.self_monitor(text, result, cognitive_context)
        # Record assistant response in conversation memory
        message = result.get("message", "")
        if message:
            self.conversation.add_turn(session_id, "assistant", str(message), language)
        if task_name:
            self.bus.publish(
                "runtime.progress",
                {"task_id": task_name, "message": "Done. I have a result.", "ok": result.get("ok", False)},
                "human_response",
            )
        return result

    async def _execute_command(self, text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        lowered = text.lower().strip()
        if self._asks_recent_work(lowered):
            return self._recent_work_response()
        if self._asks_open_last_file(lowered):
            return await self._open_last_file()
        learn_match = re.match(r"^(learn|study|update your|update|index)\s+(.+?)\.?$", lowered, flags=re.UNICODE)
        if learn_match:
            domain = learn_match.group(2).strip()
            return self.knowledge.web_learn_domain(domain)
        if lowered.startswith(("what do you know about ", "search knowledge ", "knowledge search ")):
            query = re.sub(r"^(what do you know about|search knowledge|knowledge search)\s+", "", lowered).strip()
            hits = self.knowledge.search(query, limit=5)
            return {"ok": True, "message": f"Found {len(hits)} knowledge entries for: {query}", "knowledge": hits}

        is_automation_command = (
            any(word in lowered for word in ("screenshot", "ocr", "system status", "time enna", "what time", "நேரம்", "browser", "url", "google ", "search web", "search google"))
            or lowered.startswith(("open", "launch", "start", "google "))
            or re.search(r"\b(create|write|read|delete|remove)\s+(?:a\s+|the\s+)?file\b", lowered) is not None
            or re.search(r"\bfile\s+(?:called|named)\b", lowered) is not None
        )
        if is_automation_command:
            result = await self.automation.execute(text)
            return result

        # Handle simple greetings and common commands directly for instant response
        greetings = {"hi", "hello", "hey", "hai", "à®µà®£à®•à¯à®•à®®à¯", "hallo"}
        tokens = set(re.findall(r"[\w\u0B80-\u0BFF]+", lowered, flags=re.UNICODE))
        if lowered in greetings or (bool(tokens & greetings) and len(tokens) <= 3):
            result = {"ok": True, "message": f"Hello! I'm NEXORA. How can I help you today?"}
        elif lowered.startswith("ask ") or lowered.startswith("llm ") or lowered.startswith("chat "):
            prompt = text.split(" ", 1)[1] if " " in text else text
            messages = self._chat_messages(context, text)
            messages[-1] = {"role": "user", "content": prompt}
            result = await asyncio.to_thread(self.llm.chat, messages)
        elif lowered.startswith("run workflow "):
            result = await self.workflows.run(text[13:].strip())
        elif "camera" in lowered or "webcam" in lowered:
            result = await self.agents.submit("VisionAgent", {"action": "capture"})
        elif "move cursor" in lowered or "move mouse" in lowered:
            # Parse coordinates from command
            coords = re.findall(r'\d+', text)
            if len(coords) >= 2:
                x, y = int(coords[0]), int(coords[1])
                await asyncio.to_thread(self.vision._move_mouse, x, y)
                result = {"ok": True, "message": f"Moved cursor to ({x}, {y})"}
            else:
                result = {"ok": False, "message": "Please provide coordinates like 'move cursor to 100 200'"}
        elif "click" in lowered:
            button = "right" if "right" in lowered else "left"
            await asyncio.to_thread(self.vision._click_mouse, button)
            result = {"ok": True, "message": f"Performed {button} click"}
        elif lowered.startswith("plan "):
            result = await self.agents.submit("PlannerAgent", {"goal": text[5:]})
        elif "launch" in lowered and "app" in lowered:
            # Launch application
            app_id = text.replace("launch", "").replace("app", "").strip()
            if app_id:
                result = await global_app_launcher.launch(app_id)
            else:
                result = {"ok": False, "message": "Please specify application to launch"}
        elif "terminate" in lowered and "app" in lowered:
            # Terminate application by PID
            coords = re.findall(r'\d+', text)
            if coords:
                pid = int(coords[0])
                result = await global_app_launcher.terminate(pid)
            else:
                result = {"ok": False, "message": "Please provide PID to terminate"}
        elif "list" in lowered and "apps" in lowered:
            # List applications
            result = {"ok": True, "applications": global_app_launcher.list_applications()}
        elif "list" in lowered and "running" in lowered:
            # List running applications
            result = {"ok": True, "running": global_app_launcher.list_running()}
        elif "shutdown" in lowered:
            # Shutdown system
            delay = 0
            coords = re.findall(r'\d+', text)
            if coords:
                delay = int(coords[0])
            result = await global_system_control.shutdown(delay)
        elif "restart" in lowered or "reboot" in lowered:
            # Restart system
            delay = 0
            coords = re.findall(r'\d+', text)
            if coords:
                delay = int(coords[0])
            result = await global_system_control.restart(delay)
        elif "system info" in lowered or "system status" in lowered:
            # Get system information
            result = await global_system_control.get_system_info()
        elif "list processes" in lowered or "list tasks" in lowered:
            # List running processes
            result = await global_system_control.list_processes()
        elif "kill process" in lowered:
            # Kill process by PID
            coords = re.findall(r'\d+', text)
            if coords:
                pid = int(coords[0])
                result = await global_system_control.kill_process(pid)
            else:
                result = {"ok": False, "message": "Please provide PID to kill"}
        elif "lock screen" in lowered:
            # Lock screen
            result = await global_system_control.lock_screen()
        elif "sleep" in lowered and "system" in lowered:
            # Put system to sleep
            result = await global_system_control.sleep()
        else:
            # Primary path: send to LLM via chat() with full conversation context
            relevant_memory = self.memory.search(text, limit=4)
            memory_context = "\n".join(m["summary"] for m in relevant_memory) if relevant_memory else ""
            system_parts = [self.llm.system_prompt]
            if memory_context:
                system_parts.append(f"\n[Relevant memory]\n{memory_context}")
            system = "\n".join(system_parts)
            messages = self._chat_messages(context, text)
            result = await asyncio.to_thread(self.llm.chat, messages, system=system)
        return result

    def _remember_task_result(self, text: str, result: dict[str, Any]) -> None:
        path = str(result.get("path") or "").strip()
        if path:
            self.task_context["last_file_path"] = path
        entry = {
            "timestamp": time.time(),
            "input": text,
            "ok": bool(result.get("ok")),
            "message": str(result.get("message") or result.get("error") or "")[:500],
            "path": path,
        }
        recent = list(self.task_context.get("recent", []))
        recent.append(entry)
        self.task_context["recent"] = recent[-20:]
        self.bus.set_state("tasks", {"recent": self.task_context["recent"], "last_file_path": self.task_context.get("last_file_path", "")}, "core_runtime")

    def _asks_recent_work(self, lowered: str) -> bool:
        return any(
            phrase in lowered
            for phrase in (
                "what did we do",
                "what have we done",
                "previous tasks",
                "last tasks",
                "recent tasks",
                "what you did",
                "what did you do",
            )
        )

    def _recent_work_response(self) -> dict[str, Any]:
        recent = list(self.task_context.get("recent", []))[-8:]
        if not recent:
            return {"ok": True, "message": "No completed Jarvis tasks are recorded in this runtime session yet.", "tasks": []}
        lines = []
        for item in recent:
            status = "done" if item.get("ok") else "failed"
            path = f" ({item['path']})" if item.get("path") else ""
            lines.append(f"- {status}: {item.get('input', '')}{path}")
        return {"ok": True, "message": "Recent Jarvis tasks:\n" + "\n".join(lines), "tasks": recent}

    def _asks_open_last_file(self, lowered: str) -> bool:
        if "open" not in lowered:
            return False
        return any(phrase in lowered for phrase in ("that file", "created file", "the file", "last file"))

    async def _open_last_file(self) -> dict[str, Any]:
        path = str(self.task_context.get("last_file_path") or "").strip()
        if not path:
            return {"ok": False, "message": "I do not have a previously created file to open in this session."}
        target = Path(path)
        if not target.exists():
            return {"ok": False, "message": f"The previous file no longer exists: {path}", "path": path}
        try:
            await asyncio.to_thread(os.startfile, str(target))
            return {
                "ok": True,
                "message": f"Opened the previous file: {target}",
                "path": str(target),
                "verification": {"exists": target.exists(), "is_file": target.is_file()},
                "permission_checked": True,
            }
        except Exception as exc:
            return {"ok": False, "message": f"Failed to open the previous file: {exc}", "path": path}

    @staticmethod
    def _chat_messages(context: dict[str, Any], text: str) -> list[dict[str, str]]:
        messages = [
            {"role": turn["role"], "content": turn["content"]}
            for turn in context.get("conversation_messages", [])
            if isinstance(turn, dict) and turn.get("role") in {"user", "assistant"}
            and isinstance(turn.get("content"), str)
        ][-8:]
        current = {"role": "user", "content": text}
        if not messages or messages[-1] != current:
            messages.append(current)
        return messages

    async def _voice_task(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("action", "status")
        if action == "listen":
            return await self.voice.listen(float(task.get("timeout", 12)))
        if action == "speak":
            return await self.voice.speak(str(task.get("text", "")))
        return {"ok": True, **self.voice.health()}

    def _schedule_speech(self, result: dict[str, Any], context: dict[str, Any]) -> None:
        should_speak = bool(context.get("speak")) or context.get("mode") == "voice"
        message = str(result.get("message") or "").strip()
        if not should_speak or not message:
            return
        spoken = message if len(message) <= 700 else message[:697].rstrip() + "..."
        task_name = f"voice.speak.{int(time.time() * 1000)}"
        awaitable = self.voice.speak(spoken)
        if self.async_runtime.started:
            self.async_runtime.create_task(task_name, awaitable)
        else:
            asyncio.create_task(awaitable, name=task_name)

    def _config_bool(self, key: str, default: bool = False) -> bool:
        value = self.config.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        return bool(value)

    async def _vision_task(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("action", "status")
        if action == "start":
            return await self.vision.start()
        if action == "stop":
            return await self.vision.stop()
        if action == "screen":
            return await self.vision.screen(bool(task.get("ocr", True)))
        if action == "capture":
            return await self.vision.capture()
        if action == "get_frame":
            return await self.vision.get_frame()
        if action == "get_frame_with_mouse":
            return await self.vision.get_frame_with_mouse_control()
        if action == "enable_mouse_control":
            return await self.vision.enable_mouse_control()
        if action == "disable_mouse_control":
            return await self.vision.disable_mouse_control()
        if action == "mouse_state":
            return await self.vision.get_mouse_state()
        if action == "enable_gestures":
            return await self.vision.enable_gesture_control()
        if action == "disable_gestures":
            return await self.vision.disable_gesture_control()
        if action == "capture_gestures":
            return await self.vision.capture_with_gestures()
        if action == "gesture_state":
            return await self.vision.get_gesture_state()
        return {"ok": True, **self.vision.health()}

    async def _workflow_task(self, task: dict[str, Any]) -> dict[str, Any]:
        return await self.workflows.run(str(task.get("name", "")))

    async def _execute_node(self, node_type: str, data: dict[str, Any]) -> dict[str, Any]:
        context = data.get("_context") if isinstance(data.get("_context"), dict) else {}
        last = context.get("last", {}) if isinstance(context, dict) else {}
        if node_type == "memory_save":
            text = str(data.get("text") or last.get("message") or last.get("text") or last.get("content") or "").strip()
            if not text:
                return {"ok": False, "error": "memory_save node requires text or previous node output"}
            return self.memory.store(text, "workflow", ["workflow"])
        if node_type == "voice_input":
            text = str(data.get("text", "")).strip()
            if text:
                return {"ok": True, "text": text, "language": self.voice.language(text), "source": "workflow_text"}
            return await self.voice.listen(float(data.get("timeout", 8)))
        if node_type == "llm":
            prompt = str(data.get("prompt") or last.get("text") or last.get("message") or "").strip()
            if not prompt:
                return {"ok": False, "error": "llm node requires a prompt or previous text output"}
            return self.llm.chat([{"role": "user", "content": prompt}])
        if node_type == "camera":
            return await self.vision.capture()
        if node_type == "ocr":
            return await self.vision.screen(ocr=True)
        if node_type == "agent_spawn":
            return await self.agents.submit(str(data.get("agent", "PlannerAgent")), data)
        if node_type == "browser":
            target = str(data.get("url") or data.get("text") or last.get("url") or "").strip()
            if not target:
                return {"ok": False, "error": "browser node requires a url"}
            return await self.automation.execute(f"open browser {target}")
        if node_type == "workflow_trigger":
            name = str(data.get("name", "")).strip()
            if not name:
                return {"ok": False, "error": "workflow_trigger node requires a workflow name"}
            return await self.workflows.run(name)
        if node_type == "notify":
            message = str(data.get("message") or last.get("message") or last.get("text") or "Workflow notification")
            self.bus.publish("workflow.notification", {"message": message}, "workflow_engine")
            return {"ok": True, "message": message}
        if node_type in {"trigger", "scheduler", "wait"}:
            return {"ok": True}
        self.bus.publish("workflow.node", {"type": node_type, "data": data}, "workflow_engine")
        return {"ok": False, "error": f"Unsupported workflow node type: {node_type}"}

    async def _on_voice_utterance(self, event: dict[str, Any]) -> None:
        data = event.get("data", {})
        text = data.get("text", "")
        if not text:
            return

        # Route to cognitive core but as a background task so it doesn't block event handler
        asyncio.create_task(
            self.process(text, {"mode": "voice", "language": data.get("language", "en")})
        )

    async def _on_voice_activity(self, event: dict[str, Any]) -> None:
        pass

    def _register_modules(self) -> None:
        for name, detail in [
            ("core_runtime", "Command routing and lifecycle"),
            ("human_response_engine", "Low-latency intent detection and conversational response routing"),
            ("cognitive_intelligence", "Persistent identity, unified context, multimodal perception and self-monitoring"),
            ("central_brain", "Goal, context, plan, capability selection and verification loop"),
            ("goal_manager", "Persistent goal state machine"),
            ("capability_registry", "Machine-readable runtime capability registry"),
            ("event_bus", "In-process event and state transport"),
            ("module_manager", "Module health registry"),
            ("logger", "Rotating file logger and event-bus warning mirror"),
            ("async_runtime", "Tracked asyncio task lifecycle"),
            ("health_monitor", "Startup and runtime health snapshots"),
            ("llm", "Ollama local model bridge"),
            ("memory_engine", "SQLite chunks and vector retrieval"),
            ("knowledge_manager", "Domain knowledge learning and retrieval"),
            ("agent_runtime", "Four queued agents"),
            ("workflow_engine", "Graph execution, scheduling and retries"),
            ("voice_engine", "English, Tamil and Tanglish STT/TTS"),
            ("vision_engine", "Webcam, face, OCR, objects and screen capture"),
            ("automation_engine", "Registered local actions"),
            ("ai_lab", "LLM-driven agent generation with AST validation and sandbox isolation"),
            ("companion", "iPhone Companion pairing and sync manager"),
            ("security", "API authentication, rate limiting, and audit logging"),
            ("api", "FastAPI and WebSocket bridge"),
            ("monitoring", "CPU, RAM, GPU, agents, workflows and events"),
            ("connectors", "Desktop, Browser, Terminal, Filesystem connectors"),
        ]:
            self.modules.register(name, "online", detail)

    def _register_capabilities(self) -> None:
        self.capabilities.register_capability(
            "brain.plan",
            "Planner Agent",
            "agent_runtime",
            ["plan", "inspect", "analyze", "architecture", "project"],
            risk_level="low",
        )
        self.capabilities.register_capability(
            "voice.listen_speak",
            "Voice Engine",
            "voice_engine",
            ["voice", "listen", "speak", "stt", "tts", "tamil", "tanglish"],
            permissions=["microphone", "speaker"],
            risk_level="low",
            available=self.voice.health()["stt_available"] or self.voice.health()["tts_available"],
        )
        self.capabilities.register_capability(
            "vision.capture",
            "Vision Engine",
            "vision_engine",
            ["camera", "webcam", "vision", "ocr", "screen", "object", "face"],
            permissions=["camera", "screen_capture"],
            risk_level="medium",
            available=True,
        )
        self.capabilities.register_capability(
            "workflow.execute",
            "Workflow Engine",
            "workflow_engine",
            ["workflow", "graph", "schedule", "node", "retry"],
            risk_level="medium",
        )
        self.capabilities.register_capability(
            "knowledge.learn_retrieve",
            "Knowledge Manager",
            "knowledge_manager",
            ["learn", "study", "knowledge", "domain", "index", "retrieve"],
            risk_level="low",
        )
        self.capabilities.register_capability(
            "memory.retrieve_store",
            "Memory Engine",
            "memory_engine",
            ["memory", "remember", "retrieve", "reflect", "context"],
            risk_level="low",
        )
        self.capabilities.register_capability(
            "automation.local",
            "Automation Engine",
            "automation_engine",
            ["screenshot", "time", "system", "browser", "file", "launch", "app"],
            permissions=["process_execute", "filesystem"],
            risk_level="medium",
        )
        llm_status = self.llm.status()
        self.capabilities.register_capability(
            "model.ollama",
            "Ollama Local Models",
            "llm",
            ["llm", "reasoning", "coding", "text_generation"],
            risk_level="low",
            available=bool(llm_status.get("ready")),
            health="healthy" if llm_status.get("ready") else "unavailable",
        )
        # Connector capabilities
        self.capabilities.register_capability(
            "connector.desktop",
            "Desktop Connector",
            "connector_manager",
            ["launch_app", "list_apps", "system_info", "lock_screen"],
            permissions=["process_execute"],
            risk_level="medium",
            available=self.connector_manager.get("desktop").health() in ("AVAILABLE", "DEGRADED"),
        )
        self.capabilities.register_capability(
            "connector.browser",
            "Browser Connector",
            "connector_manager",
            ["open_url", "search_web", "get_page_title"],
            risk_level="low",
            available=True,
        )
        self.capabilities.register_capability(
            "connector.terminal",
            "Terminal Connector",
            "connector_manager",
            ["run_command", "check_allowlist"],
            permissions=["process_execute"],
            risk_level="high",
            available=True,
        )
        self.capabilities.register_capability(
            "connector.filesystem",
            "Filesystem Connector",
            "connector_manager",
            ["read_file", "write_file", "list_dir", "file_exists", "create_dir", "delete_file"],
            permissions=["filesystem_read", "filesystem_write"],
            risk_level="high",
            available=True,
        )
        self.capabilities.register_capability(
            "connector.android",
            "Android Connector",
            "connector_manager",
            ["adb_command", "list_devices", "install_apk", "launch_app_android"],
            permissions=["process_execute"],
            risk_level="medium",
            available=True,
        )
        self.capabilities.register_capability(
            "connector.vscode",
            "VS Code Connector",
            "connector_manager",
            ["open_file", "open_workspace", "install_extension"],
            risk_level="low",
            available=self.connector_manager.get("vscode").health() == "AVAILABLE",
        )
        llm_ready = bool(self.llm.status().get("ready"))
        self.capabilities.register_capability(
            "ai_lab.generate_agent",
            "AI Lab Agent Generator",
            "ai_lab",
            ["generate_agent", "validate_code", "sandbox_agent", "register_agent"],
            risk_level="medium",
            available=True,
            health="healthy" if llm_ready else "degraded",
        )

def configure_logging(root: Path) -> None:
    (root / "logs").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(root / "logs" / "nexora.log", encoding="utf-8"), logging.StreamHandler()],
    )
