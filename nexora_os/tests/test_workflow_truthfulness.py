import asyncio

from nexora_os.backend.core.event_bus import EventBus
from nexora_os.backend.workflows.engine import WorkflowEngine


def run(coro):
    return asyncio.run(coro)


def test_workflow_engine_requires_executor_for_capability_nodes(tmp_path):
    bus = EventBus()
    engine = WorkflowEngine(tmp_path / "workflows.db", bus)
    engine.save(
        {
            "name": "truthful_memory",
            "description": "memory nodes must not fake success",
            "retries": 0,
            "graph": {
                "nodes": [{"id": "save", "type": "memory_save", "data": {"text": "remember this"}}],
                "edges": [],
            },
        }
    )

    result = run(engine.run("truthful_memory"))

    assert result["ok"] is False
    assert "No executor registered for node type: memory_save" in result["error"]
    assert result["completed"] == []
    trace = engine.trace("truthful_memory", result["run_id"])
    assert trace[-1]["status"] == "failed"
    assert trace[-1]["node_type"] == "memory_save"


def test_workflow_engine_uses_registered_executor_outputs(tmp_path):
    bus = EventBus()
    engine = WorkflowEngine(tmp_path / "workflows.db", bus)

    async def executor(node_type, data):
        if node_type == "memory_save":
            return {"ok": True, "stored": True, "text": data["text"]}
        return {"ok": False, "error": f"unexpected {node_type}"}

    engine.node_executor = executor
    engine.save(
        {
            "name": "real_memory",
            "description": "executor-backed memory node succeeds",
            "retries": 0,
            "graph": {
                "nodes": [{"id": "save", "type": "memory_save", "data": {"text": "remember this"}}],
                "edges": [],
            },
        }
    )

    result = run(engine.run("real_memory"))

    assert result["ok"] is True
    assert result["completed"] == ["save"]
    assert result["outputs"]["save"] == {"ok": True, "stored": True, "text": "remember this"}


def test_workflow_notify_publishes_real_event_without_runtime_executor(tmp_path):
    bus = EventBus()
    received = []
    bus.subscribe("workflow.notification", lambda event: received.append(event))
    engine = WorkflowEngine(tmp_path / "workflows.db", bus)
    engine.save(
        {
            "name": "notify_user",
            "description": "notify uses event bus instead of fake completion",
            "retries": 0,
            "graph": {
                "nodes": [{"id": "n1", "type": "notify", "data": {"message": "Done"}}],
                "edges": [],
            },
        }
    )

    result = run(engine.run("notify_user"))

    assert result["ok"] is True
    assert result["outputs"]["n1"]["message"] == "Done"
    assert received
    assert received[-1].payload["message"] == "Done"
