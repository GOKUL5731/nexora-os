from .process_adapter import ProcessBackedAdapter
import asyncio
import shutil
from typing import Any


class CodexAdapter(ProcessBackedAdapter):
    executable_names = ("codex", "codex.exe")
    # The installed Windows Codex desktop shell currently identifies its
    # process as ChatGPT.exe. This detects presence only; it does not imply a
    # supported prompt transport.
    process_tokens = ("codex", "chatgpt")

    def __init__(self) -> None:
        super().__init__()
        self.workspace_path = ""
        self.prompt_process: asyncio.subprocess.Process | None = None
        self._output = ""
        self._output_drained = False

    def discover(self) -> dict[str, Any]:
        result = super().discover()
        cli = shutil.which("codex") or shutil.which("codex.exe")
        result["codex_cli"] = bool(cli)
        result["codex_cli_path"] = cli or ""
        result["capabilities"]["send_prompt"] = bool(cli)
        result["capabilities"]["observe_output"] = bool(cli)
        result["capabilities"]["detect_completion"] = bool(cli)
        return result

    async def launch(self, workspace_path: str = "") -> dict[str, Any]:
        if not self.discover().get("codex_cli"):
            return {"ok": False, "status": "UNAVAILABLE", "error": "codex_cli_not_found"}
        self.workspace_path = workspace_path
        return {"ok": True, "status": "READY", "workspace_path": workspace_path, "transport": "codex_exec"}

    async def send_prompt(self, prompt: str) -> dict[str, Any]:
        if not self.workspace_path:
            return {"ok": False, "status": "FAILED", "error": "workspace_not_attached"}
        if self.prompt_process and self.prompt_process.returncode is None:
            return {"ok": False, "status": "BUSY", "error": "prompt_already_running"}
        try:
            self._output = ""
            self._output_drained = False
            self.prompt_process = await asyncio.create_subprocess_exec(
                "codex", "exec", "--cd", self.workspace_path, "--json", "--sandbox", "workspace-write", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            return {"ok": True, "status": "DELIVERED", "transport": "codex_exec", "pid": self.prompt_process.pid, "verified": True}
        except OSError as exc:
            return {"ok": False, "status": "FAILED", "error": str(exc)}

    async def observe_output(self) -> dict[str, Any]:
        if not self.prompt_process:
            return {"ok": True, "state": "READY", "output": "", "verified": True}
        if self.prompt_process.stdout:
            try:
                chunk = await asyncio.wait_for(self.prompt_process.stdout.read(4096), timeout=0.05)
                if chunk:
                    self._output += chunk.decode("utf-8", errors="replace")
            except asyncio.TimeoutError:
                pass
        returncode = self.prompt_process.returncode
        if returncode is None:
            return {"ok": True, "state": "WORKING", "output": self._output, "verified": True}
        if not self._output_drained:
            remaining, _ = await self.prompt_process.communicate()
            if remaining:
                self._output += remaining.decode("utf-8", errors="replace")
            self._output_drained = True
        state = "COMPLETED" if returncode == 0 else "FAILED"
        return {"ok": returncode == 0, "state": state, "exit_code": returncode, "output": self._output, "verified": True}

    def detect_completion(self) -> bool:
        return bool(self.prompt_process and self.prompt_process.returncode is not None)

    async def close(self) -> bool:
        if self.prompt_process and self.prompt_process.returncode is None:
            self.prompt_process.terminate()
            await self.prompt_process.wait()
            return True
        return False
