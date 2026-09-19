from __future__ import annotations

import asyncio
import shutil
from typing import Any

import psutil

from .generic import ApplicationAdapter


class ProcessBackedAdapter(ApplicationAdapter):
    """Honest baseline adapter for applications without a supported API.

    Process discovery is real. Prompt injection and response extraction remain
    unavailable until an application-specific API/UIA integration is present.
    """

    executable_names: tuple[str, ...] = ()
    process_tokens: tuple[str, ...] = ()

    def __init__(self) -> None:
        self.process: asyncio.subprocess.Process | None = None
        self._attached_pid: int | None = None

    def _running(self) -> list[psutil.Process]:
        found: list[psutil.Process] = []
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                name = (proc.info.get("name") or "").lower()
                exe = (proc.info.get("exe") or "").lower()
                if any(token in name or token in exe for token in self.process_tokens):
                    found.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return found

    def discover(self) -> dict[str, Any]:
        running = self._running()
        commands = [name for name in self.executable_names if shutil.which(name)]
        return {
            "installed": bool(commands) or bool(running),
            "running": bool(running),
            "pids": [proc.pid for proc in running],
            "launch_commands": commands,
            "capabilities": {
                "discover": True,
                "launch": bool(commands),
                "attach": bool(running),
                "send_prompt": False,
                "observe_output": False,
                "detect_waiting": False,
                "detect_completion": False,
            },
        }

    async def launch(self, workspace_path: str = "") -> dict[str, Any]:
        command = next((name for name in self.executable_names if shutil.which(name)), None)
        if not command:
            return {"ok": False, "status": "UNAVAILABLE", "error": "executable_not_found"}
        args = [command]
        if workspace_path:
            args.append(workspace_path)
        try:
            self.process = await asyncio.create_subprocess_exec(*args)
            return {"ok": True, "status": "STARTED", "pid": self.process.pid, "verified": True}
        except (OSError, RuntimeError) as exc:
            return {"ok": False, "status": "FAILED", "error": str(exc)}

    async def attach(self, window_id: str) -> bool:
        try:
            pid = int(window_id)
        except (TypeError, ValueError):
            return False
        if any(proc.pid == pid for proc in self._running()):
            self._attached_pid = pid
            return True
        return False

    async def send_prompt(self, prompt: str) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "UNAVAILABLE",
            "error": "prompt_transport_not_implemented",
            "detail": "No supported application API or UI Automation transport is configured.",
        }

    async def observe_output(self) -> dict[str, Any]:
        running = self._running()
        return {
            "ok": True,
            "state": "RUNNING" if running else "STOPPED",
            "verified": True,
            "observable_output": False,
        }

    def detect_waiting(self) -> bool:
        return False

    def detect_completion(self) -> bool:
        return False

    async def close(self) -> bool:
        if self.process and self.process.returncode is None:
            self.process.terminate()
            await self.process.wait()
            return self.process.returncode is not None
        return False
