from fastapi.testclient import TestClient

from nexora_os.backend.api.app import app
from nexora_os.backend.core.event_bus import EventBus
from nexora_os.backend.knowledge.manager import KnowledgeManager
from nexora_os.backend.learning.manager import LearningManager
from nexora_os.backend.memory.engine import MemoryEngine


def _manager(tmp_path):
    bus = EventBus()
    memory = MemoryEngine(tmp_path / "memory.db", bus)
    knowledge = KnowledgeManager(tmp_path / "knowledge.db", memory, bus)
    learning = LearningManager(tmp_path / "learning.db", bus, knowledge, memory)
    return learning, memory


def test_learning_job_indexes_tests_and_records_episode(tmp_path):
    learning, memory = _manager(tmp_path)
    result = learning.start_job(
        "sqlite",
        "Learn SQLite transaction basics",
        resources=[
            {
                "title": "SQLite transactions",
                "content": "SQLite supports ACID transactions with commit, rollback, and isolation behavior.",
                "source": "local fixture",
                "tags": ["database", "transaction"],
            }
        ],
        expected_terms=["acid", "rollback"],
    )

    assert result["ok"] is True
    job = result["job"]
    assert job["status"] == "PASSED"
    assert job["result"]["self_test"]["passed"] is True
    assert memory.list_episodes("SQLite transaction basics", outcome="success")


def test_learning_job_persists_and_reports_failed_self_test(tmp_path):
    learning, memory = _manager(tmp_path)
    result = learning.start_job(
        "graph theory",
        resources=[
            {
                "title": "Graphs",
                "content": "Graphs contain vertices and edges.",
                "source": "local fixture",
                "tags": ["math"],
            }
        ],
        expected_terms=["eigenvalue"],
    )

    assert result["ok"] is False
    assert result["job"]["status"] == "FAILED"
    assert result["job"]["result"]["self_test"]["checks"][0]["passed"] is False
    assert memory.list_episodes("learn_domain:graph theory", outcome="failed")

    reloaded = LearningManager(learning.database, EventBus(), learning.knowledge, memory)
    assert reloaded.get_job(result["job"]["id"])["status"] == "FAILED"


def test_learning_jobs_api_contract():
    with TestClient(app) as client:
        response = client.post(
            "/learning/jobs",
            json={
                "domain": "learning api fixture",
                "goal": "Verify learning API route",
                "resources": [
                    {
                        "title": "Learning API",
                        "content": "The learning API creates jobs, stores knowledge, and verifies recall.",
                        "source": "test fixture",
                        "tags": ["api", "recall"],
                    }
                ],
                "expected_terms": ["recall"],
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["job"]["status"] == "PASSED"

        fetched = client.get(f"/learning/jobs/{payload['job']['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["domain"] == "learning api fixture"

        listed = client.get("/learning/jobs")
        assert listed.status_code == 200
        assert listed.json()["status"]["jobs"]["PASSED"] >= 1


def test_learning_jobs_api_returns_failed_job_without_server_error():
    with TestClient(app) as client:
        response = client.post(
            "/learning/jobs",
            json={
                "domain": "learning api failure fixture",
                "resources": [
                    {
                        "title": "Short fixture",
                        "content": "This fixture only mentions retrieval.",
                        "source": "test fixture",
                        "tags": ["api"],
                    }
                ],
                "expected_terms": ["nonexistent-calibration-token"],
            },
        )
        assert response.status_code == 200
        assert response.json()["ok"] is False
        assert response.json()["job"]["status"] == "FAILED"
