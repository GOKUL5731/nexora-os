from __future__ import annotations

import ast
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from ..core.event_bus import EventBus

FORBIDDEN_IMPORTS = {"subprocess", "socket", "ctypes", "winreg", "shutil"}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__", "open"}


class AgentCreator:
    def __init__(self, sandbox: Path, registry: Path, bus: EventBus) -> None:
        self.sandbox = sandbox
        self.registry = registry
        self.bus = bus
        sandbox.mkdir(parents=True, exist_ok=True)
        registry.parent.mkdir(parents=True, exist_ok=True)
        if not registry.exists():
            registry.write_text("[]", encoding="utf-8")

    def create(self, goal: str, name: str = "") -> dict[str, Any]:
        safe_name = re.sub(r"[^A-Za-z0-9_]", "", name or self._name(goal))
        if not safe_name.endswith("Agent"):
            safe_name += "Agent"
        code = self._template(safe_name, goal)
        validation = self.validate(code)
        if not validation["ok"]:
            return {"ok": False, "stage": "validate", **validation}
        session = self.sandbox / f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{safe_name}"
        session.mkdir(parents=True)
        source = session / "agent.py"
        manifest = session / "manifest.json"
        source.write_text(code, encoding="utf-8")
        manifest.write_text(json.dumps({"name": safe_name, "goal": goal, "validated": True, "executed": False}, indent=2), encoding="utf-8")
        registry = json.loads(self.registry.read_text(encoding="utf-8"))
        entry = {"name": safe_name, "goal": goal, "sandbox": str(session), "status": "registered", "deployed": False, "executed": False}
        registry = [item for item in registry if item["name"] != safe_name] + [entry]
        self.registry.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        result = {"ok": True, "flow": ["goal", "template", "generate", "validate", "sandbox", "register"], **entry}
        self.bus.publish("ai_lab.agent_registered", result, "agent_creator")
        self.bus.set_state("ai_lab", {"agents": registry}, "agent_creator")
        return result

    def validate(self, code: str) -> dict[str, Any]:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return {"ok": False, "errors": [f"Syntax error: {exc.msg}"]}
        errors: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                        errors.append(f"Forbidden import: {alias.name}")
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in FORBIDDEN_IMPORTS:
                errors.append(f"Forbidden import: {node.module}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                errors.append(f"Forbidden call: {node.func.id}")
        return {"ok": not errors, "errors": errors, "executed": False}

    def list(self) -> list[dict[str, Any]]:
        return json.loads(self.registry.read_text(encoding="utf-8"))

    @staticmethod
    def _name(goal: str) -> str:
        words = re.findall(r"[A-Za-z0-9]+", goal.title())[:3]
        return "".join(words) or "Generated"

    @staticmethod
    def _template(name: str, goal: str) -> str:
        return (
            "from __future__ import annotations\n\n"
            f"class {name}:\n"
            f"    \"\"\"Generated template for: {goal.replace(chr(34), chr(39))}\"\"\"\n\n"
            "    async def execute(self, task: dict, context: list[dict]) -> dict:\n"
            "        return {\"ok\": True, \"task\": task, \"context_count\": len(context)}\n"
        )
