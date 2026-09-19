from backend.core.event_bus import EventBus
from backend.security.manager import SecurityManager


def test_emergency_stop_blocks_connector_execution(tmp_path):
    manager = SecurityManager(tmp_path / "security.db", EventBus())
    assert manager.execution_allowed("desktop", "list_windows")[0] is True
    manager.emergency_stop("test")
    assert manager.execution_allowed("desktop", "launch_app") == (False, "emergency_stop_active")
    manager.clear_emergency_stop()
    assert manager.execution_allowed("desktop", "list_windows")[0] is True
