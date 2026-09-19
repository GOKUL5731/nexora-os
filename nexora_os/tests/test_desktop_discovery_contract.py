from backend.connectors.desktop import DesktopConnector, STATUS_DEGRADED, sys_platform


def test_monitor_discovery_is_explicitly_degraded_off_windows():
    connector = DesktopConnector()
    result = connector.list_monitors()
    if sys_platform() == "win32":
        assert "monitors" in result
        assert isinstance(result["monitors"], list)
    else:
        assert result["ok"] is False
        assert result["status"] == STATUS_DEGRADED
        assert result["monitors"] == []


def test_monitor_action_is_exposed():
    connector = DesktopConnector()
    assert "list_monitors" in connector.get_capabilities()
