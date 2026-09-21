from fastapi.testclient import TestClient

from nexora_os.backend.api import app as app_module
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


def test_agent_generation_reports_config_policy_when_disabled():
    with TestClient(app) as client:
        previous = dict(app_module.runtime.config._config)
        app_module.runtime.config._config["agent_creation_enabled"] = False
        response = client.post(
            "/agents/build",
            json={"description": "report memory health safely", "name": "SmokeReporter"},
        )
        app_module.runtime.config._config = previous

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["enabled"] is False
    assert payload["detail"]["config_keys"]["enable"] == "agent_creation_enabled"


def test_agent_generation_enabled_creates_validated_sandbox_agent():
    with TestClient(app) as client:
        previous = dict(app_module.runtime.config._config)
        app_module.runtime.config._config["agent_creation_enabled"] = True
        app_module.runtime.config._config["agent_creation_template_fallback"] = True
        response = client.post(
            "/agents/build",
            json={"description": "report memory health safely", "name": "SmokeReporter"},
        )
        app_module.runtime.config._config = previous

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["name"] == "SmokeReporterAgent"
    assert payload["source_method"] in {"llm", "template"}
    assert payload["policy"]["enabled"] is True
    assert payload["policy"]["reason"] == ""
    assert payload["sandbox"]
    assert "SmokeReporterAgent" in {agent["name"] for agent in app_module.runtime.creator.list()}
