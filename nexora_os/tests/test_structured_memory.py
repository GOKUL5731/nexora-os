from fastapi.testclient import TestClient

from nexora_os.backend.api.app import app
from nexora_os.backend.core.event_bus import EventBus
from nexora_os.backend.memory.engine import MemoryEngine


def test_episode_memory_persists_across_restart(tmp_path):
    bus = EventBus()
    db = tmp_path / "memory.db"
    memory = MemoryEngine(db, bus)
    created = memory.record_episode(
        "learn the connector state",
        "observed adapter diagnostics",
        "codex transport was available",
        outcome="success",
        evidence=[{"source": "test", "status": "passed"}],
        importance=0.9,
        tags=["orchestration"],
    )

    assert created["ok"] is True
    memory._pool.close_all()

    reloaded = MemoryEngine(db, bus)
    episodes = reloaded.list_episodes("connector", outcome="success")

    assert len(episodes) == 1
    assert episodes[0]["goal"] == "learn the connector state"
    assert episodes[0]["evidence"][0]["status"] == "passed"
    assert episodes[0]["importance"] == 0.9
    reloaded._pool.close_all()


def test_procedure_memory_versions_and_scores(tmp_path):
    memory = MemoryEngine(tmp_path / "memory.db", EventBus())
    first = memory.upsert_procedure(
        "Verify Codex transport",
        "Run a non-destructive codex exec probe",
        ["create temp git workspace", "run codex exec", "inspect exit code"],
        validators=["exit_code == 0", "no files changed"],
        source_evidence=[{"kind": "live_test"}],
        confidence=0.55,
        tags=["codex"],
    )
    second = memory.upsert_procedure(
        "Verify Codex transport",
        "Run a bounded codex exec probe and drain JSONL output",
        ["create temp git workspace", "run codex exec --json", "verify output and filesystem"],
        validators=["exit_code == 0", "output contains READY", "git status clean"],
    )

    assert first["procedure"]["version"] == 1
    assert second["procedure"]["version"] == 2

    scored = memory.score_procedure(second["procedure"]["id"], True, {"test": "passed"})
    assert scored["ok"] is True
    assert scored["procedure"]["success_count"] == 1
    assert scored["procedure"]["failure_count"] == 0

    procedures = memory.list_procedures("Codex")
    assert procedures[0]["version"] == 2
    memory._pool.close_all()


def test_structured_memory_api_contract():
    with TestClient(app) as client:
        episode = client.post(
            "/memory/episodes",
            json={
                "goal": "remember API event",
                "action": "called structured memory route",
                "result": "episode persisted",
                "outcome": "success",
                "evidence": [{"route": "/memory/episodes"}],
                "tags": ["api"],
            },
        )
        assert episode.status_code == 200
        assert episode.json()["episode"]["outcome"] == "success"

        procedure = client.post(
            "/memory/procedures",
            json={
                "name": "Structured memory API check",
                "description": "Validate procedural API storage",
                "steps": ["post procedure", "read procedure"],
                "validators": ["HTTP 200"],
                "tags": ["api"],
            },
        )
        assert procedure.status_code == 200
        procedure_id = procedure.json()["procedure"]["id"]

        scored = client.post(
            f"/memory/procedures/{procedure_id}/score",
            json={"succeeded": True, "evidence": {"route": "score"}},
        )
        assert scored.status_code == 200
        assert scored.json()["procedure"]["success_count"] >= 1

        episodes = client.get("/memory/episodes", params={"query": "API event", "outcome": "success"})
        assert episodes.status_code == 200
        assert any(item["goal"] == "remember API event" for item in episodes.json()["episodes"])
