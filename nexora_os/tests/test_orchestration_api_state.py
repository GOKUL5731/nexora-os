import pytest

from backend.orchestration.project_orchestrator import ProjectOrchestrator
from backend.orchestration.workspace_manager import WorkspaceManager
from backend.core.event_bus import EventBus


@pytest.mark.asyncio
async def test_snapshot_exposes_waiting_unavailable_workers(tmp_path):
    bus = EventBus()
    orchestrator = ProjectOrchestrator(bus, WorkspaceManager(tmp_path / "workspaces"))
    project_id = await orchestrator.start_project(
        "state-test", str(tmp_path), "inspect", ["codex"]
    )
    project = orchestrator.get_project(project_id)
    assert project is not None
    assert project["status"] in {"WAITING", "EXECUTING"}
    assert project["tasks"][0]["status"] in {"WAITING", "FAILED", "STARTED"}
    assert orchestrator.snapshot()["count"] == 1
    await orchestrator.stop()
    await bus.shutdown()
