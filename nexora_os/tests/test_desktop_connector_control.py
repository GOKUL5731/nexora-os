from __future__ import annotations

import sys
import time
from pathlib import Path

from nexora_os.backend.connectors.desktop import ApplicationRecord, DesktopConnector


def test_desktop_connector_discovers_and_resolves_known_apps() -> None:
    connector = DesktopConnector()

    discovered = connector.execute("discover_apps", {"force": True})
    assert discovered["ok"] is True
    assert discovered["count"] >= 1

    resolved = connector.execute("resolve_app", {"app_name": "notepad"})
    assert resolved["ok"] is True
    assert resolved["application"]["application_id"] == "notepad"
    assert "launch" in resolved["application"]["capabilities"]


def test_desktop_connector_launches_and_verifies_real_process() -> None:
    connector = DesktopConnector()
    python_exe = Path(sys.executable)
    script = "import time; time.sleep(8)"

    connector._registry["jarvis-test-python"] = ApplicationRecord(
        application_id="jarvis-test-python",
        name="Jarvis Test Python",
        executable=python_exe.name,
        path=str(python_exe),
        process_names=[python_exe.name],
        capabilities=["launch", "process_observe"],
        status="available",
    )
    connector._last_discovery = time.time()

    result = connector.execute(
        "launch_app",
        {
            "app_name": "jarvis-test-python",
            "args": ["-c", script],
            "wait_seconds": 3,
        },
    )
    try:
        assert result["ok"] is True
        assert result["verification"]["verified"] is True
        assert result["verification"]["process_detected"] is True
        assert result["permission_checked"] is True
        assert result["observation"]["process"]["found"] is True
    finally:
        pid = result.get("pid")
        if pid:
            connector.execute("close_app", {"pid": pid})


def test_desktop_connector_audit_records_action_result() -> None:
    connector = DesktopConnector()

    connector.execute("resolve_app", {"app_name": "notepad"})
    audit = connector.execute("audit_log", {})

    assert audit["ok"] is True
    assert audit["entries"]
    last = audit["entries"][-1]
    assert last["action"] in {"resolve_app", "audit_log"}
    assert "duration_ms" in last
