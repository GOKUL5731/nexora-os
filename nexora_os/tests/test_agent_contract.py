import asyncio

from fastapi.testclient import TestClient

from nexora_os.backend.agents.runtime import AgentRuntime, PlannerAgent
from nexora_os.backend.api.app import app
from nexora_os.backend.core.event_bus import EventBus
from nexora_os.backend.memory.engine import MemoryEngine


async def _ok_handler(task):
    return {"ok": True, "message": "delegated", "task": task}


def test_planner_agent_class_exists_and_returns_bounded_plan(tmp_path):
    bus = EventBus()
    memory = MemoryEngine(tmp_path / "memory.db", bus)
    agent = PlannerAgent("PlannerAgent", bus, memory)

    result = asyncio.run(agent.execute({"goal": "inspect runtime health"}, []))

    assert result["ok"] is True
    assert result["message"].startswith("Plan ready")
    assert result["plan"]
    assert result["verification_required"] is True
    assert result["llm_powered"] in {True, False}


def test_agent_runtime_exposes_four_recovery_agents(tmp_path):
    bus = EventBus()
    memory = MemoryEngine(tmp_path / "memory.db", bus)
    runtime = AgentRuntime(bus, memory, _ok_handler, _ok_handler, _ok_handler, recovery_enabled=False)

    names = {item["name"] for item in runtime.health()}

    assert names == {"PlannerAgent", "VoiceAgent", "VisionAgent", "WorkflowAgent"}
    assert len(names) == 4


def test_unproven_agents_are_not_active_runtime_agents(tmp_path):
    bus = EventBus()
    memory = MemoryEngine(tmp_path / "memory.db", bus)
    runtime = AgentRuntime(bus, memory, _ok_handler, _ok_handler, _ok_handler, recovery_enabled=False)

    async def submit(name):
        return await runtime.submit(name, {"goal": "do risky work"})

    for name in ("AutonomousAgent", "ResearchAgent", "CodingAgent"):
        result = asyncio.run(submit(name))
        assert result["ok"] is False
        assert result["error"] == f"Unknown agent: {name}"


def test_agents_api_returns_four_unique_runtime_agents():
    with TestClient(app) as client:
        response = client.get("/agents")

    assert response.status_code == 200
    payload = response.json()
    names = [item["name"] for item in payload["runtime_agents"]]
    assert names == ["PlannerAgent", "VoiceAgent", "VisionAgent", "WorkflowAgent"]
    assert payload["tool_agents"] == payload["runtime_agents"]
