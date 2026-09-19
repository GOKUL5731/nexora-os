from backend.computer.app_adapters.codex import CodexAdapter
from backend.orchestration.project_orchestrator import ProjectOrchestrator
from backend.orchestration.workspace_manager import WorkspaceManager
from backend.core.event_bus import EventBus


def test_codex_diagnostics_distinguish_detection_from_prompt_transport(monkeypatch):
    adapter = CodexAdapter()
    monkeypatch.setattr(adapter, "_running", lambda: [])
    monkeypatch.setattr("shutil.which", lambda _: None)
    result = adapter.discover()
    assert result["installed"] is False
    assert result["capabilities"]["send_prompt"] is False


def test_orchestrator_exposes_adapter_diagnostics(tmp_path):
    orchestrator = ProjectOrchestrator(EventBus(), WorkspaceManager(tmp_path / "workspaces"))
    status = orchestrator.adapter_status()
    assert set(status) == {"cursor", "codex", "antigravity"}
    assert all("capabilities" in value for value in status.values())
