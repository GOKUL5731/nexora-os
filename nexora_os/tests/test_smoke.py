from fastapi.testclient import TestClient

from nexora_os.backend.api.app import app


def test_core_routes_return_ok():
    with TestClient(app) as client:
        for path in (
            "/status",
            "/health",
            "/agents",
            "/workflows",
            "/memory",
            "/voice/status",
            "/vision/status",
            "/automation",
            "/settings",
        ):
            response = client.get(path)
            assert response.status_code == 200, path


def test_generation_flows_do_not_execute_generated_agent_code():
    with TestClient(app) as client:
        response = client.post(
            "/agents/build",
            json={"description": "report memory health safely", "name": "SmokeReporter"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["executed"] is False
