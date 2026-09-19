from __future__ import annotations

import asyncio
import logging
import uuid
import shutil
import os
from typing import Any
from pathlib import Path

logger = logging.getLogger("nexora.orchestration.workspace")

class WorkspaceManager:
    """
    Manages isolated Git worktrees/branches for safe multi-agent parallel coding.
    Falls back to directory copying when Git is not available.
    """
    def __init__(self, base_workspace_dir: Path):
        self.base_dir = base_workspace_dir
        self.workspaces: dict[str, dict[str, Any]] = {}
        
        if not self.base_dir.exists():
            self.base_dir.mkdir(parents=True, exist_ok=True)

    async def _run_cmd(self, cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode or 0, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
        except Exception as e:
            return -1, "", str(e)

    async def create_workspace(self, project_id: str, name: str, source_path: str) -> dict[str, Any]:
        """Creates a sandboxed workspace for a project using Git worktree if possible."""
        ws_id = str(uuid.uuid4())[:8]
        target_path = self.base_dir / f"ws_{ws_id}_{name}"
        branch_name = f"g-agent-{ws_id}"
        
        is_git = (Path(source_path) / ".git").exists()
        used_git = False

        if is_git:
            # Create git branch and worktree
            code, out, err = await self._run_cmd(["git", "worktree", "add", "-b", branch_name, str(target_path)], cwd=source_path)
            if code == 0:
                used_git = True
                logger.info(f"Created Git worktree at {target_path} on branch {branch_name}")
            else:
                logger.warning(f"Git worktree creation failed ({err.strip()}), falling back to directory creation.")

        if not used_git:
            target_path.mkdir(parents=True, exist_ok=True)

        ws_info = {
            "id": ws_id,
            "project_id": project_id,
            "name": name,
            "source_path": source_path,
            "sandbox_path": str(target_path),
            "branch_name": branch_name if used_git else None,
            "is_git": used_git,
            "status": "CREATED"
        }

        self.workspaces[ws_id] = ws_info
        return ws_info

    async def get_workspace_diff(self, ws_id: str) -> dict[str, Any]:
        """Returns modified files and diff details for a workspace."""
        ws = self.workspaces.get(ws_id)
        if not ws:
            return {"modified_files": [], "diff": ""}

        sandbox_path = ws["sandbox_path"]
        if ws.get("is_git"):
            code, out, err = await self._run_cmd(["git", "status", "--porcelain"], cwd=sandbox_path)
            lines = [line.strip()[3:] for line in out.splitlines() if line.strip()]
            _, diff_text, _ = await self._run_cmd(["git", "diff"], cwd=sandbox_path)
            return {"modified_files": lines, "diff": diff_text}
        else:
            # Walk directory to find files
            files = []
            for root, _, filenames in os.walk(sandbox_path):
                for f in filenames:
                    rel = os.path.relpath(os.path.join(root, f), sandbox_path)
                    files.append(rel)
            return {"modified_files": files, "diff": ""}

    async def remove_workspace(self, ws_id: str) -> bool:
        """Cleans up a workspace."""
        ws = self.workspaces.get(ws_id)
        if not ws:
            return False

        sandbox_path = ws["sandbox_path"]
        if ws.get("is_git"):
            source_path = ws["source_path"]
            await self._run_cmd(["git", "worktree", "remove", "--force", sandbox_path], cwd=source_path)
            if ws.get("branch_name"):
                await self._run_cmd(["git", "branch", "-D", ws["branch_name"]], cwd=source_path)
        else:
            if Path(sandbox_path).exists():
                shutil.rmtree(sandbox_path, ignore_errors=True)

        self.workspaces.pop(ws_id, None)
        logger.info(f"Removed workspace {ws_id}")
        return True

    def get_workspace(self, ws_id: str) -> dict[str, Any] | None:
        return self.workspaces.get(ws_id)
