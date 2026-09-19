from backend.orchestration.project_store import ProjectStore
from backend.core.event_bus import EventBus
from backend.orchestration.project_orchestrator import ProjectOrchestrator
from backend.orchestration.workspace_manager import WorkspaceManager


def test_project_store_round_trip(tmp_path):
    store = ProjectStore(tmp_path / "orchestration.db")
    project = {
        "project_id": "p1",
        "name": "demo",
        "status": "WAITING",
        "tasks": [{"id": "t1", "status": "WAITING"}],
    }
    store.save(project)
    assert store.load_all() == [project]


def test_orchestrator_recovery_marks_external_work_unknown(tmp_path):
    store = ProjectStore(tmp_path / "orchestration.db")
    store.save({
        "project_id": "p2", "name": "recover", "status": "EXECUTING",
        "tasks": [{"id": "t1", "status": "STARTED"}],
    })
    orchestrator = ProjectOrchestrator(EventBus(), WorkspaceManager(tmp_path / "workspaces"), store)
    recovered = orchestrator.get_project("p2")
    assert recovered["status"] == "WAITING"
    assert recovered["tasks"][0]["status"] == "WAITING"
    assert "rediscovered" in recovered["tasks"][0]["waiting_reason"]
