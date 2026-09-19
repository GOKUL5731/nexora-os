from __future__ import annotations

import asyncio
import logging
from typing import Any
import uuid
from datetime import datetime

from ..core.event_bus import EventBus
from .workspace_manager import WorkspaceManager
from .conflict_manager import ConflictManager
from ..computer.app_adapters import CursorAdapter, CodexAdapter, AntigravityAdapter

logger = logging.getLogger("nexora.orchestration.project")

class ProjectOrchestrator:
    """
    Central supervisor for coordinating multiple autonomous workers (Codex, Cursor, Antigravity)
    on a shared workspace with safe Git worktree isolation and conflict management.
    """
    def __init__(self, bus: EventBus, workspace_manager: WorkspaceManager):
        self.bus = bus
        self.workspace_manager = workspace_manager
        self.conflict_manager = ConflictManager()
        self.active_projects: dict[str, dict[str, Any]] = {}
        self._loop_task: asyncio.Task | None = None
        
        self.adapters = {
            "cursor": CursorAdapter(),
            "codex": CodexAdapter(),
            "antigravity": AntigravityAdapter()
        }
        
        self.bus.subscribe("task.created", self._handle_task_created)

    async def start(self) -> None:
        self._loop_task = asyncio.create_task(self._orchestration_loop())
        logger.info("Project Orchestrator started.")

    async def stop(self) -> None:
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

    async def start_project(self, project_name: str, root_path: str, goal: str, target_workers: list[str]) -> str:
        """Starts a new multi-agent orchestrated project."""
        project_id = str(uuid.uuid4())
        workspace = await self.workspace_manager.create_workspace(project_id, project_name, root_path)
        
        self.active_projects[project_id] = {
            "project_id": project_id,
            "name": project_name,
            "goal": goal,
            "status": "PLANNING",
            "workspace_id": workspace["id"],
            "root_path": root_path,
            "target_workers": target_workers,
            "worker_workspaces": {},
            "tasks": [],
            "conflict_report": None,
            "created_at": datetime.utcnow().isoformat()
        }
        
        self.bus.publish("orchestrator.project_started", {"project_id": project_id, "name": project_name}, "orchestrator")
        await self._decompose_and_assign(project_id)
        return project_id

    async def _decompose_and_assign(self, project_id: str) -> None:
        project = self.active_projects[project_id]
        workers = project["target_workers"]
        # Worker worktrees must branch from the real repository path.  Passing the
        # workspace id here silently created empty fallback directories and made
        # external-agent work impossible to verify.
        root_path = project["root_path"]
        
        logger.info(f"Decomposing goal for project {project_id} across {len(workers)} workers.")
        
        for i, worker in enumerate(workers):
            # Create a separate isolated workspace for each worker
            worker_ws = await self.workspace_manager.create_workspace(project_id, f"{worker}_{i}", root_path)
            project["worker_workspaces"][worker] = worker_ws["id"]

            task_id = str(uuid.uuid4())
            task = {
                "id": task_id,
                "project_id": project_id,
                "worker_application": worker,
                "workspace_id": worker_ws["id"],
                "status": "PENDING",
                "description": f"Assigned chunk {i+1} for {worker}"
            }
            project["tasks"].append(task)
            
            adapter = self.adapters.get(worker.lower())
            if adapter:
                health = adapter.discover()
                if health.get("installed"):
                    launch_result = await adapter.launch(worker_ws["sandbox_path"])
                    if launch_result.get("ok", False):
                        task["status"] = "STARTED"
                        task["launch_evidence"] = launch_result
                        prompt_result = await adapter.send_prompt(task["description"])
                        task["prompt_evidence"] = prompt_result
                        if not prompt_result.get("ok", False):
                            task["status"] = "FAILED"
                            task["failure"] = "Application rejected prompt"
                    else:
                        task["status"] = "WAITING"
                        task["waiting_reason"] = "Application launch was not verified"
                else:
                    task["status"] = "WAITING"
                    task["waiting_reason"] = "Application is unavailable"
            else:
                task["status"] = "WAITING"
                task["waiting_reason"] = "No adapter registered"

            self.bus.publish("orchestrator.task_assigned", task, "orchestrator")

        project["status"] = "EXECUTING"

    async def _orchestration_loop(self) -> None:
        """Background loop to monitor worker progress and re-prompt if stalled."""
        try:
            while True:
                await asyncio.sleep(5.0)
                await self._check_progress()
        except asyncio.CancelledError:
            logger.info("Orchestration loop cancelled.")

    async def _check_progress(self) -> None:
        for pid, project in self.active_projects.items():
            if project["status"] != "EXECUTING":
                continue
                
            all_done = True
            for task in project["tasks"]:
                if task["status"] not in ("COMPLETED", "FAILED"):
                    all_done = False
                
            if all_done:
                project["status"] = "VERIFYING"
                self.bus.publish("orchestrator.project_verifying", {"project_id": pid}, "orchestrator")
                
                # Gather diffs across all worker workspaces and run ConflictManager
                workspace_diffs = {}
                for worker, ws_id in project["worker_workspaces"].items():
                    workspace_diffs[ws_id] = await self.workspace_manager.get_workspace_diff(ws_id)

                conflict_report = await self.conflict_manager.analyze_and_resolve(
                    project.get("workspace_id", ""),
                    workspace_diffs
                )
                project["conflict_report"] = conflict_report

                project["status"] = "COMPLETED" if not conflict_report["has_conflicts"] else "NEEDS_RESOLUTION"
                self.bus.publish("orchestrator.project_completed", {
                    "project_id": pid,
                    "has_conflicts": conflict_report["has_conflicts"],
                    "conflict_report": conflict_report
                }, "orchestrator")

    async def _handle_task_created(self, event: dict[str, Any]) -> None:
        pass
