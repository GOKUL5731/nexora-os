from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from ..agents.runtime import AgentRuntime
from ..ai_lab.agent_creator import AgentCreator
from ..automation.engine import AutomationEngine
from ..automation.scheduler import global_scheduler
from ..automation.application_launcher import global_app_launcher
from ..automation.autonomous_executor import global_autonomous_executor
from ..automation.system_control import global_system_control
from ..memory.engine import MemoryEngine
from ..vision.engine import VisionEngine
from ..voice.engine import VoiceEngine
from ..workflows.engine import WorkflowEngine
from .event_bus import EventBus
from .async_runtime import AsyncRuntime
from .health_monitor import HealthMonitor
from .llm import OllamaClient
from .logger import configure_core_logging
from .module_manager import ModuleManager
from .validation import validate_and_sanitize, ValidationError
from .aliases import expand_command


class NexoraRuntime:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.bus = EventBus()
        self.log = configure_core_logging(root, self.bus)
        self.modules = ModuleManager(self.bus)
        self.async_runtime = AsyncRuntime(self.bus)
        self.llm = OllamaClient()
        self.memory = MemoryEngine(root / "databases" / "memory.db", self.bus)
        self.voice = VoiceEngine(self.bus)
        self.vision = VisionEngine(root / "logs" / "captures", self.bus)
        self.automation = AutomationEngine(self.bus, self.vision)
        self.workflows = WorkflowEngine(root / "databases" / "workflows.db", self.bus)
        self.creator = AgentCreator(root / "ai_lab_sandbox", root / "databases" / "generated_agents.json", self.bus)
        self.agents = AgentRuntime(
            self.bus,
            self.memory,
            self._voice_task,
            self._vision_task,
            self._workflow_task,
        )
        self.monitor = HealthMonitor(self.bus, self.modules, self.agents, self.workflows, self.memory, self.async_runtime)
        self.workflows.node_executor = self._execute_node
        self._register_modules()

    async def start(self) -> None:
        await self.async_runtime.start()
        await global_scheduler.start()  # Start task scheduler
        self.workflows.start()
        self.agents.sync()
        self.workflows.sync()
        self.bus.set_state("voice", self.voice.health(), "runtime")
        self.bus.set_state("vision", self.vision.health(), "runtime")
        self.bus.set_state("automation", self.automation.status(), "runtime")
        self.bus.set_state("ai_lab", {"agents": self.creator.list()}, "runtime")
        self.bus.publish("runtime.started", {"status": "online"}, "core_runtime")
        self.log.info("NEXORA runtime started")

    async def shutdown(self) -> None:
        self.log.info("NEXORA runtime shutdown requested")
        await global_scheduler.stop()  # Stop task scheduler
        await self.workflows.stop()
        await self.agents.shutdown()
        await self.async_runtime.shutdown()
        self.bus.publish("runtime.stopped", {"status": "stopped"}, "core_runtime")

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
        
        # Expand command aliases
        text = expand_command(text)
        
        self.memory.store(text, "episodic", ["command"])
        lowered = text.lower().strip()
        
        # Handle simple greetings and common commands directly for instant response
        greetings = ["hi", "hello", "hey", "hai", "வணக்கம்", "hallo"]
        if any(greeting in lowered for greeting in greetings):
            result = {"ok": True, "message": f"Hello! I'm NEXORA. How can I help you today?"}
        elif lowered.startswith("ask ") or lowered.startswith("llm "):
            prompt = text.split(" ", 1)[1] if " " in text else text
            result = self.llm.generate(prompt)
        elif lowered.startswith("run workflow "):
            result = await self.workflows.run(text[13:].strip())
        elif any(word in lowered for word in ("screenshot", "ocr", "system status", "time enna", "what time", "நேரம்", "open ", "launch ", "start ", "create file", "read file", "write file", "delete file", "remove file", "browser", "url")) or lowered.startswith(("open", "launch", "start")):
            result = await self.automation.execute(text)
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
            # Route everything to the AutonomousAgent which handles LLM + tool execution
            # It will use the LLM when online, or fall back to a structured plan when offline
            result = await self.agents.submit("AutonomousAgent", {"goal": text, "context": context})

        message = result.get("message") or ("Completed." if result.get("ok") else result.get("error", "Command failed."))
        response = {"type": "success" if result.get("ok", False) else "error", "message": message, **result}
        self.memory.store(message, "semantic", ["response"])
        self.bus.publish("runtime.response", response, "core_runtime")
        return response

    async def _voice_task(self, task: dict[str, Any]) -> dict[str, Any]:
        action = task.get("action", "status")
        if action == "listen":
            return await self.voice.listen(float(task.get("timeout", 12)))
        if action == "speak":
            return await self.voice.speak(str(task.get("text", "")))
        return {"ok": True, **self.voice.health()}

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
        if node_type == "memory_save":
            return self.memory.store(str(data.get("text", "")), "workflow", ["workflow"])
        if node_type in {"camera", "ocr"}:
            return await self.vision.screen(ocr=node_type == "ocr")
        if node_type == "agent_spawn":
            return await self.agents.submit(str(data.get("agent", "PlannerAgent")), data)
        if node_type == "wait":
            return {"ok": True}
        self.bus.publish("workflow.node", {"type": node_type, "data": data}, "workflow_engine")
        return {"ok": True}

    def _register_modules(self) -> None:
        for name, detail in [
            ("core_runtime", "Command routing and lifecycle"),
            ("event_bus", "In-process event and state transport"),
            ("module_manager", "Module health registry"),
            ("logger", "Rotating file logger and event-bus warning mirror"),
            ("async_runtime", "Tracked asyncio task lifecycle"),
            ("health_monitor", "Startup and runtime health snapshots"),
            ("llm", "Ollama local model bridge"),
            ("memory_engine", "SQLite chunks and vector retrieval"),
            ("agent_runtime", "Four queued agents"),
            ("workflow_engine", "Graph execution, scheduling and retries"),
            ("voice_engine", "English, Tamil and Tanglish STT/TTS"),
            ("vision_engine", "Webcam, face, OCR, objects and screen capture"),
            ("automation_engine", "Registered local actions"),
            # AI Lab disabled until base system is stable per recovery requirements
            # ("ai_lab", "Validated non-executing agent generation"),
            ("api", "FastAPI and WebSocket bridge"),
            ("monitoring", "CPU, RAM, GPU, agents, workflows and events"),
        ]:
            self.modules.register(name, "online", detail)


def configure_logging(root: Path) -> None:
    (root / "logs").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(root / "logs" / "nexora.log", encoding="utf-8"), logging.StreamHandler()],
    )
