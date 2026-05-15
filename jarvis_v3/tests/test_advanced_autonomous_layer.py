"""Advanced autonomous intelligence layer tests.

Run:
  python -X utf8 tests/test_advanced_autonomous_layer.py
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def temp_db(name: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix="jarvis_advanced_"))
    return root / f"{name}.db"


async def test_planning_and_collaboration_execute_real_queue():
    from core.collaboration_engine import CollaborationEngine
    from core.planner_engine import PlanningEngine

    planner = PlanningEngine(db_path=temp_db("planning"))
    collab = CollaborationEngine(db_path=temp_db("collaboration"))
    plan = planner.create_plan("Build a new vision plugin", {"language": "python"})

    assert_true(len(plan["tasks"]) == 7, "plugin goal should expand into seven tasks")
    assert_true(plan["tasks"][0]["agent"] == "researcher", "first task should be research")
    assert_true(plan["tasks"][-1]["dependencies"], "deployment should depend on previous work")

    result = await planner.execute_plan(plan["id"], collab, concurrency=2)
    assert_true(result["status"] == "completed", f"plan should complete: {result['status']}")
    assert_true(all(t["status"] == "completed" for t in result["tasks"]), "all tasks should complete")
    assert_true(collab.receive_messages("commander"), "agents should message commander on completion")


async def test_agent_communication_and_concurrency_stress():
    from core.collaboration_engine import CollaborationEngine

    collab = CollaborationEngine(db_path=temp_db("collaboration_stress"))

    async def coding_handler(task: str, context: dict) -> dict:
        await asyncio.sleep(0.01)
        return {"handled": task, "index": context["index"]}

    collab.register_agent("coder", "Coding Agent", ("code", "implement"), coding_handler)
    collab.send_message("planner", "coder", "Use the shared coding convention.")
    collab.set_shared_memory("coding_standard", {"style": "focused"}, "planner")

    for idx in range(30):
        collab.submit_task(f"implement unit {idx}", "coder", {"index": idx})

    results = await collab.run_queued(concurrency=8)
    assert_true(len(results) == 30, "all queued tasks should run")
    assert_true(all(r["status"] == "completed" for r in results), "stress tasks should complete")
    assert_true(collab.get_shared_memory("coding_standard")["style"] == "focused", "shared memory should work")


async def test_workflow_generation_validation_and_execution():
    from core.workflow_generator import WorkflowGenerator

    generator = WorkflowGenerator(db_path=temp_db("workflow_generation"))
    for action in ["research topic", "summarize notes", "research topic", "summarize notes", "notify user"]:
        generator.record_action(action)

    suggestions = generator.suggest_from_patterns(min_count=2)
    assert_true(suggestions, "repeated actions should produce workflow suggestions")

    spec = generator.generate_from_goal("notify then wait", "safe_notify_wait")
    assert_true(generator.validate_workflow(spec), "generated workflow should validate")
    result = await generator.execute_generated(spec)
    assert_true(result["status"] == "success", f"generated workflow should execute: {result}")


def test_prediction_context_and_proactive_assistance():
    from core.contextual_awareness import ContextualAwarenessEngine
    from core.prediction_engine import PredictiveIntelligenceEngine
    from core.proactive_engine import ProactiveAssistanceEngine

    class DummyRNN:
        def __init__(self):
            self.events = []

        def record_event(self, event, context=""):
            self.events.append(event)

        def predict_next(self, context_events=None, top_k=5):
            return {"predictions": [{"command": "open_vscode", "confidence": 0.8}]}

    prediction = PredictiveIntelligenceEngine(rnn_engine=DummyRNN(), db_path=temp_db("prediction"))
    for action in ["open_vscode", "run_tests", "open_vscode", "run_tests"]:
        prediction.record_action(action)
    pred = prediction.predict(["open_vscode"])
    assert_true(pred["top"]["action"] == "run_tests" or pred["top"]["action"] == "open_vscode", "prediction should return learned actions")

    context = ContextualAwarenessEngine()
    context.record_action("debug code in vscode")
    ctx = context.current_context()
    suggestions = ProactiveAssistanceEngine().evaluate(ctx, pred)
    assert_true(suggestions, "proactive engine should emit suggestions")


async def test_reflection_detects_failures_and_slow_modules():
    from core.reflection_engine import CognitiveReflectionEngine

    reflection = CognitiveReflectionEngine({"reflection": {"slow_ms": 50}}, db_path=temp_db("reflection"))
    reflection.observe("planner", "execute", "failed", error="dependency missing")
    reflection.observe("planner", "execute", "failed", error="dependency missing")
    reflection.observe("workflow", "run", "success", latency_ms=100)
    cycle = await reflection.run_cycle(lambda: {"benchmark": "ok"})
    assert_true(cycle["analysis"]["repeated_failures"], "reflection should detect repeated failures")
    assert_true(cycle["analysis"]["slow_modules"], "reflection should detect slow modules")
    assert_true(cycle["improvement_plan"], "reflection should produce an improvement plan")


def test_evolution_scoring_and_rollback():
    from core.evolution_engine import AdvancedEvolutionEngine

    evolution = AdvancedEvolutionEngine(db_path=temp_db("evolution"))
    mutations = evolution.mutate_prompt("test_prompt", "Answer helpfully.")
    scored = evolution.score_mutation(mutations[0]["id"])
    assert_true(scored["score"] > 0, "mutation should be scored")

    target = Path(tempfile.mkdtemp(prefix="jarvis_deploy_")) / "prompt.txt"
    target.write_text("original", encoding="utf-8")
    deployment = evolution.deploy_variant(scored["id"], target)
    assert_true(target.read_text(encoding="utf-8") != "original", "deployment should write variant")
    rollback = evolution.rollback(deployment["deployment_id"])
    assert_true(rollback["rolled_back"], "rollback should report success")
    assert_true(target.read_text(encoding="utf-8") == "original", "rollback should restore original")


async def test_distributed_reasoning_and_knowledge_memory():
    from core.advanced_memory import AdvancedMemorySystem
    from core.distributed_reasoning import DistributedReasoningEngine
    from core.knowledge_graph import KnowledgeGraph
    from core.planner_engine import PlanningEngine

    reasoning = DistributedReasoningEngine()
    answer = await reasoning.reason("Plan and implement code for a workflow plugin")
    assert_true("routes" in answer and len(answer["routes"]) >= 2, "distributed reasoning should use multiple routes")

    memory = AdvancedMemorySystem(db_path=temp_db("advanced_memory"))
    memory.remember_episode("test", "episode one", {"ok": True})
    memory.store_fact("semantic", "answer", 42)
    memory.store_procedure("test_proc", {"steps": [{"action": "log"}]})
    memory.remember_for_agent("planner", "preference", {"depth": "high"})
    assert_true(memory.recall_episodes(1)[0]["summary"] == "episode one", "episodic memory should work")
    assert_true(memory.get_fact("semantic", "answer") == 42, "semantic memory should work")
    assert_true(memory.get_procedure("test_proc"), "procedural memory should work")
    assert_true(memory.recall_for_agent("planner", "preference")["depth"] == "high", "agent memory should work")

    graph = KnowledgeGraph(db_path=temp_db("graph"))
    plan = PlanningEngine(db_path=temp_db("graph_plan")).create_plan("Automate research workflow")
    graph.ingest_plan(plan)
    snapshot = graph.snapshot()
    assert_true(snapshot["nodes"] and snapshot["edges"], "knowledge graph should store plan relationships")


async def test_autonomous_orchestration_vertical_slice():
    from core.orchestration_engine import AutonomousOrchestrationEngine

    temp = Path(tempfile.mkdtemp(prefix="jarvis_orch_"))
    cfg = {
        "planning": {"db_path": str(temp / "planning.db")},
        "collaboration": {"db_path": str(temp / "collaboration.db")},
        "workflow_generator": {"db_path": str(temp / "workflow_gen.db")},
        "prediction": {"db_path": str(temp / "prediction.db")},
        "reflection": {"db_path": str(temp / "reflection.db"), "slow_ms": 1_000_000},
        "evolution": {"db_path": str(temp / "evolution.db")},
        "advanced_memory": {"db_path": str(temp / "advanced_memory.db")},
        "knowledge_graph": {"db_path": str(temp / "graph.db")},
    }
    engine = AutonomousOrchestrationEngine(cfg)
    result = await engine.handle_goal("Build a new vision plugin", {"language": "python"}, execute=True)
    assert_true(result["plan"]["status"] == "completed", "orchestrator should execute a full plan")
    tick = await engine.cognitive_tick()
    assert_true("suggestions" in tick, "cognitive tick should produce proactive state")


async def main():
    tests = [
        test_planning_and_collaboration_execute_real_queue,
        test_agent_communication_and_concurrency_stress,
        test_workflow_generation_validation_and_execution,
        test_prediction_context_and_proactive_assistance,
        test_reflection_detects_failures_and_slow_modules,
        test_evolution_scoring_and_rollback,
        test_distributed_reasoning_and_knowledge_memory,
        test_autonomous_orchestration_vertical_slice,
    ]
    passed = 0
    for test in tests:
        if inspect.iscoroutinefunction(test):
            await test()
        else:
            test()
        passed += 1
        print(f"PASS {test.__name__}")
    print(f"\nADVANCED AUTONOMY tests: {passed}/{len(tests)} passed")


if __name__ == "__main__":
    asyncio.run(main())
