from __future__ import annotations

import asyncio
import logging
from typing import Any
import uuid
from datetime import datetime

from ..core.event_bus import EventBus
from .workspace_manager import WorkspaceManager
from .conflict_manager import ConflictManager
from .project_store import ProjectStore
from .external_session import ExternalAgentSession, SessionState
from ..computer.app_adapters import CursorAdapter, CodexAdapter, AntigravityAdapter

logger = logging.getLogger("nexora.orchestration.project")

class ProjectOrchestrator:
    """
    Central supervisor for coordinating multiple autonomous workers (Codex, Cursor, Antigravity)
    on a shared workspace with safe Git worktree isolation and conflict management.
    """
    def __init__(self, bus: EventBus, workspace_manager: WorkspaceManager, store: ProjectStore | None = None):
        self.bus = bus
        self.workspace_manager = workspace_manager
        self.conflict_manager = ConflictManager()
        self.active_projects: dict[str, dict[str, Any]] = {}
        self.store = store
        self._loop_task: asyncio.Task | None = None
        
        self.adapters = {
            "cursor": CursorAdapter(),
            "codex": CodexAdapter(),
            "antigravity": AntigravityAdapter()
        }
        
        self.bus.subscribe("task.created", self._handle_task_created)
        if self.store:
            for project in self.store.load_all():
                # External processes and windows cannot be assumed alive after a restart.
                for task in project.get("tasks", []):
                    if task.get("status") in {"STARTED", "PENDING"}:
                        task["status"] = "WAITING"
                        task["waiting_reason"] = "Recovered after G restart; external session must be rediscovered"
                if project.get("status") in {"PLANNING", "EXECUTING"}:
                    project["status"] = "WAITING"
                self.active_projects[project["project_id"]] = project

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

    def snapshot(self) -> dict[str, Any]:
        """Return serializable canonical project state for API/UI consumers."""
        projects = []
        for project in self.active_projects.values():
            item = dict(project)
            item["tasks"] = [dict(task) for task in project.get("tasks", [])]
            projects.append(item)
        return {"projects": projects, "count": len(projects)}

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        project = self.active_projects.get(project_id)
        if not project:
            return None
        item = dict(project)
        item["tasks"] = [dict(task) for task in project.get("tasks", [])]
        return item

    def _persist(self, project_id: str) -> None:
        if self.store and project_id in self.active_projects:
            self.store.save(self.active_projects[project_id])

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
            "sessions": {},
            "conflict_report": None,
            "created_at": datetime.utcnow().isoformat()
        }
        self._persist(project_id)
        
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
            session = ExternalAgentSession(worker.lower(), project_id, task_id, worker_ws["id"])
            task["session_id"] = session.session_id
            project["sessions"][session.session_id] = session.to_dict()
            project["tasks"].append(task)
            
            adapter = self.adapters.get(worker.lower())
            if adapter:
                health = adapter.discover()
                if health.get("installed"):
                    session.transition(SessionState.LAUNCHING)
                    launch_result = await adapter.launch(worker_ws["sandbox_path"])
                    if launch_result.get("ok", False):
                        session.transition(SessionState.READY)
                        task["status"] = "STARTED"
                        task["launch_evidence"] = launch_result
                        prompt_result = await adapter.send_prompt(task["description"])
                        session.transition(SessionState.PROMPTING)
                        session.record_prompt(task["description"], "ACCEPTED" if prompt_result.get("ok") else "REJECTED", prompt_result)
                        task["prompt_evidence"] = prompt_result
                        if not prompt_result.get("ok", False):
                            task["status"] = "FAILED"
                            task["failure"] = "Application rejected prompt"
                            session.transition(SessionState.FAILED, task["failure"])
                        else:
                            session.transition(SessionState.WORKING)
                    else:
                        task["status"] = "WAITING"
                        task["waiting_reason"] = "Application launch was not verified"
                        session.transition(SessionState.WAITING, task["waiting_reason"])
                else:
                    task["status"] = "WAITING"
                    task["waiting_reason"] = "Application is unavailable"
                    session.transition(SessionState.WAITING, task["waiting_reason"])
            else:
                task["status"] = "WAITING"
                task["waiting_reason"] = "No adapter registered"
                session.transition(SessionState.WAITING, task["waiting_reason"])

            project["sessions"][session.session_id] = session.to_dict()

            self.bus.publish("orchestrator.task_assigned", task, "orchestrator")
            self._persist(project_id)

        project["status"] = "EXECUTING" if any(
            task["status"] == "STARTED" for task in project["tasks"]
        ) else "WAITING"
        self.bus.publish("orchestrator.project_state_changed", {
            "project_id": project_id,
            "status": project["status"],
            "tasks": project["tasks"],
        }, "orchestrator")
        self._persist(project_id)

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
            if project["status"] not in ("EXECUTING", "WAITING"):
                continue
                
            all_done = True
            for task in project["tasks"]:
                if task["status"] not in ("COMPLETED", "FAILED", "WAITING"):
                    all_done = False
                
            if all_done and any(task["status"] in ("COMPLETED", "FAILED") for task in project["tasks"]):
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
                self._persist(pid)
                self.bus.publish("orchestrator.project_completed", {
                    "project_id": pid,
                    "has_conflicts": conflict_report["has_conflicts"],
                    "conflict_report": conflict_report
                }, "orchestrator")

    async def _handle_task_created(self, event: dict[str, Any]) -> None:
        pass
