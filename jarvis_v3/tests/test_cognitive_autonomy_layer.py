"""Persistent cognitive autonomy layer tests.

Run:
  python -X utf8 tests/test_cognitive_autonomy_layer.py
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
    root = Path(tempfile.mkdtemp(prefix="jarvis_cognitive_"))
    return root / f"{name}.db"


def test_goal_manager_persistence_and_dependencies():
    from core.goal_manager import GoalManager

    db = temp_db("goals")
    manager = GoalManager(db_path=db)
    base = manager.create_goal("Improve startup speed", "optimization", priority=9)
    child = manager.create_goal("Benchmark startup path", "learning", priority=8, dependencies=[base["id"]])

    ready = manager.next_goals()
    assert_true(ready[0]["id"] == base["id"], "base goal should be ready first")
    manager.update_progress(base["id"], 1.0)
    ready = manager.next_goals()
    assert_true(any(goal["id"] == child["id"] for goal in ready), "child goal should unblock after dependency completes")

    reloaded = GoalManager(db_path=db)
    assert_true(reloaded.get_goal(base["id"])["status"] == "completed", "goals should persist")


def test_simulation_engine_sandbox_and_risk():
    from core.planner_engine import PlanningEngine
    from core.simulation_engine import SimulationEngine

    planner = PlanningEngine(db_path=temp_db("planning"))
    plan = planner.create_plan("Build a safe workflow plugin")
    simulation = SimulationEngine(db_path=temp_db("simulation"))
    result = simulation.simulate_plan(plan)
    assert_true("resource_impact" in result["outcome"], "plan simulation should estimate resources")
    assert_true(result["risk_score"] < 1, "normal plan should have bounded risk")

    trial = simulation.sandbox_trial("compile_ok", {"main.py": "print('ok')\n"}, entry="main.py")
    assert_true(trial["passed"], "sandbox trial should execute valid python")


async def test_society_reputation_and_concurrent_assignment():
    from core.collaboration_engine import CollaborationEngine
    from core.society_engine import AgentSocietyEngine

    collab = CollaborationEngine(db_path=temp_db("collab"))
    society = AgentSocietyEngine(collaboration=collab, db_path=temp_db("society"))
    society.record_outcome("coder", "implement code workflow", True, quality=0.9)

    async def assign(idx: int):
        return society.assign_task(f"implement code unit {idx}")

    results = await asyncio.gather(*(assign(i) for i in range(20)))
    assert_true(all(r["selected_agent"] for r in results), "society should assign every task")
    assert_true(society.get_agent("coder")["reputation"] > 0.6, "successful outcomes should raise reputation")


def test_world_model_graph_reasoning_and_validation():
    from core.goal_manager import GoalManager
    from core.graph_reasoning import GraphReasoningEngine
    from core.knowledge_graph import KnowledgeGraph
    from core.world_model_engine import WorldModelEngine

    graph = KnowledgeGraph(db_path=temp_db("graph"))
    world = WorldModelEngine(graph=graph)
    goals = GoalManager(db_path=temp_db("goals"))
    goal = goals.create_goal("Optimize workflow latency", "optimization")
    world.observe_system()
    world.update_goal_map([goal])
    graph.connect("device:local", goal["id"], "supports")

    reasoning = GraphReasoningEngine(graph=graph)
    validation = reasoning.validate()
    assert_true(validation["valid"], "world graph should validate")
    assert_true(world.snapshot()["nodes"], "world snapshot should expose graph nodes")


async def test_research_skills_resources_healing_and_personality():
    from core.advanced_memory import AdvancedMemorySystem
    from core.adaptive_personality import AdaptivePersonalityEngine
    from core.autonomous_research import AutonomousResearchEngine
    from core.module_manager import ModuleManager
    from core.resource_orchestrator import ResourceOrchestrator
    from core.self_healing_engine import SelfHealingEngine
    from core.skill_evolution import SkillEvolutionEngine

    research_root = Path(tempfile.mkdtemp(prefix="jarvis_research_"))
    (research_root / "notes.md").write_text("workflow latency optimization uses benchmark evidence", encoding="utf-8")
    memory = AdvancedMemorySystem(db_path=temp_db("advanced_memory"))
    research = AutonomousResearchEngine(db_path=temp_db("research"), root=research_root, memory=memory)
    report = await research.research("workflow latency optimization")
    assert_true(report["findings"], "research should gather local evidence")

    skills = SkillEvolutionEngine(db_path=temp_db("skills"))
    skill = skills.record_result("prediction_accuracy", 0.8)
    assert_true(skill["score"] > 0.5, "positive reward should improve skill score")

    resources = ResourceOrchestrator({"resources": {"max_cached_models": 1}})
    resources.cache_model("small")
    cache = resources.cache_model("large")
    assert_true("small" in cache["evicted"], "model cache should evict least recently used entries")

    modules = ModuleManager()
    state = {"count": 0}

    def restart():
        state["count"] += 1
        return {"ok": True}

    modules.register("recoverable", status="failed", restart=restart)
    healing = SelfHealingEngine(modules=modules)
    result = healing.self_heal_cycle()
    assert_true(result["recoveries"][0]["ok"], "self-healing should restart recoverable modules")
    assert_true(state["count"] == 1, "restart callback should run exactly once")

    personality = AdaptivePersonalityEngine(db_path=temp_db("personality"))
    profile = personality.observe_interaction("Please be brief and test first.")
    assert_true(profile["detail_level"]["value"] == "concise", "personality should learn detail preference")


async def test_orchestrated_cognitive_loop_and_ui_snapshots():
    from core.orchestration_engine import AutonomousOrchestrationEngine
    from ui.cognitive_map import CognitiveMapPanel
    from ui.evolution_dashboard import EvolutionDashboard
    from ui.society_dashboard import SocietyDashboard
    from ui.workflow_intelligence import WorkflowIntelligencePanel

    temp = Path(tempfile.mkdtemp(prefix="jarvis_orch_cognitive_"))
    cfg = {
        "planning": {"db_path": str(temp / "planning.db")},
        "collaboration": {"db_path": str(temp / "collaboration.db")},
        "workflow_generator": {"db_path": str(temp / "workflow_gen.db")},
        "prediction": {"db_path": str(temp / "prediction.db")},
        "reflection": {"db_path": str(temp / "reflection.db"), "slow_ms": 1_000_000},
        "evolution": {"db_path": str(temp / "evolution.db")},
        "advanced_memory": {"db_path": str(temp / "advanced_memory.db")},
        "knowledge_graph": {"db_path": str(temp / "graph.db")},
        "goals": {"db_path": str(temp / "goals.db")},
        "simulation": {"db_path": str(temp / "simulation.db")},
        "society": {"db_path": str(temp / "society.db")},
        "skill_evolution": {"db_path": str(temp / "skills.db")},
        "research": {"db_path": str(temp / "research.db")},
        "personality_adaptation": {"db_path": str(temp / "personality.db")},
    }
    engine = AutonomousOrchestrationEngine(cfg)
    result = await engine.handle_goal("Build a new workflow plugin", {"language": "python"}, execute=True)
    assert_true(result["simulation"]["passed"], "goal execution should include passing simulation")
    tick = await engine.cognitive_tick()
    assert_true(tick["cycle"]["status"] == "completed", "cognitive loop should complete one cycle")
    assert_true("resources" in tick, "cognitive tick should expose resources")

    assert_true(CognitiveMapPanel(engine).snapshot()["nodes"], "cognitive map should expose nodes")
    assert_true(SocietyDashboard(engine).snapshot()["agents"], "society dashboard should expose agents")
    assert_true("skills" in EvolutionDashboard(engine).snapshot(), "evolution dashboard should expose skills")
    assert_true("resources" in WorkflowIntelligencePanel(engine).snapshot(), "workflow panel should expose resources")


async def main():
    tests = [
        test_goal_manager_persistence_and_dependencies,
        test_simulation_engine_sandbox_and_risk,
        test_society_reputation_and_concurrent_assignment,
        test_world_model_graph_reasoning_and_validation,
        test_research_skills_resources_healing_and_personality,
        test_orchestrated_cognitive_loop_and_ui_snapshots,
    ]
    passed = 0
    for test in tests:
        if inspect.iscoroutinefunction(test):
            await test()
        else:
            test()
        passed += 1
        print(f"PASS {test.__name__}")
    print(f"\nCOGNITIVE AUTONOMY tests: {passed}/{len(tests)} passed")


if __name__ == "__main__":
    asyncio.run(main())
