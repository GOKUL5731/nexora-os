"""Persistent digital cognitive ecosystem tests.

Run:
  python -X utf8 tests/test_meta_cognitive_ecosystem.py
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
    root = Path(tempfile.mkdtemp(prefix="jarvis_meta_"))
    return root / f"{name}.db"


def meta_config(root: Path) -> dict:
    return {
        "planning": {"db_path": str(root / "planning.db")},
        "collaboration": {"db_path": str(root / "collaboration.db")},
        "workflow_generator": {"db_path": str(root / "workflow_gen.db")},
        "prediction": {"db_path": str(root / "prediction.db")},
        "reflection": {"db_path": str(root / "reflection.db"), "slow_ms": 1_000_000},
        "evolution": {"db_path": str(root / "evolution.db")},
        "advanced_memory": {"db_path": str(root / "advanced_memory.db")},
        "knowledge_graph": {"db_path": str(root / "graph.db")},
        "goals": {"db_path": str(root / "goals.db")},
        "simulation": {"db_path": str(root / "simulation.db")},
        "society": {"db_path": str(root / "society.db")},
        "skill_evolution": {"db_path": str(root / "skills.db")},
        "research": {"db_path": str(root / "research.db")},
        "personality_adaptation": {"db_path": str(root / "personality.db")},
        "strategies": {"db_path": str(root / "strategies.db")},
        "digital_twins": {"db_path": str(root / "twins.db")},
        "meta_cognition": {"db_path": str(root / "meta.db")},
        "simulation_universe": {"db_path": str(root / "universe.db")},
        "long_horizon": {"db_path": str(root / "horizon.db")},
        "knowledge_synthesis": {"db_path": str(root / "synthesis.db")},
        "architecture_optimizer": {"db_path": str(root / "architecture.db")},
        "cognitive_health": {"db_path": str(root / "health.db")},
        "self_stability": {"db_path": str(root / "stability.db")},
        "evolutionary_memory": {"db_path": str(root / "evolutionary_memory.db")},
    }


def test_strategy_marketplace_benchmarks_and_switching():
    from core.strategy_manager import CognitiveStrategyManager

    manager = CognitiveStrategyManager(db_path=temp_db("strategies"))
    results = [manager.benchmark_strategy(s["name"], {"task": "code plugin", "resource_pressure": 0.2}) for s in manager.list_strategies()]
    assert_true(all(0 <= r["score"] <= 1 for r in results), "strategy scores should be normalized")
    selected = manager.choose_strategy({"task": "debug code plugin", "resource_pressure": 0.1})
    assert_true(selected["name"] in {s["name"] for s in manager.list_strategies()}, "selected strategy should exist")


def test_digital_twins_simulate_failures():
    from core.digital_twin_engine import DigitalTwinEngine

    twins = DigitalTwinEngine(db_path=temp_db("twins"))
    twins.upsert_twin("system", "local", {"pressure_score": 0.4}, confidence=0.8)
    outcome = twins.simulate_twin_outcome("system", "local", {"pressure_score": 0.95})
    assert_true(outcome["risk_score"] > 0.5, "high pressure twin change should increase risk")
    twins.upsert_twin("workflow", "active_goals", {"status_counts": {"blocked": 2}}, confidence=0.7)
    assert_true(twins.predict_failures(), "twins should predict blocked workflow failures")


def test_simulation_universe_concurrency_and_architecture_validation():
    from core.simulation_universe import SimulationUniverse

    universe = SimulationUniverse(db_path=temp_db("universe"))
    scenarios = [
        {"type": "architecture", "scenario": {"components": [{"name": "a"}], "rollback_plan": True, "tests": ["unit"]}},
        {"type": "agent_coordination", "scenario": {"agents": [{"trust": 0.8}], "tasks": ["a", "b"]}},
        {"type": "workflow", "scenario": {"name": "safe", "steps": [{"action": "log", "params": {}}]}},
    ]
    results = universe.run_batch(scenarios, concurrency=3)
    assert_true(len(results) == 3, "simulation universe should run all scenarios")
    assert_true(any(r["passed"] for r in results), "at least one simulation should pass")


def test_self_stability_checkpoint_and_rollback():
    from core.self_stability_engine import SelfStabilityEngine

    root = Path(tempfile.mkdtemp(prefix="jarvis_stability_root_"))
    (root / "core").mkdir()
    target = root / "core" / "sample.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    stability = SelfStabilityEngine(db_path=temp_db("stability"), root=root)
    baseline = stability.record_integrity_snapshot(["core"])
    checkpoint = stability.create_checkpoint("sample", ["core/sample.py"])
    target.write_text("VALUE = 2\n", encoding="utf-8")
    integrity = stability.verify_integrity(baseline["id"], ["core"])
    assert_true(integrity["changes"], "integrity check should detect modified file")
    rollback = stability.rollback_checkpoint(checkpoint["id"])
    assert_true(rollback["rolled_back"], "checkpoint rollback should succeed")
    assert_true(target.read_text(encoding="utf-8") == "VALUE = 1\n", "rollback should restore original content")


def test_long_horizon_synthesis_and_cognitive_health():
    from core.advanced_memory import AdvancedMemorySystem
    from core.cognitive_health import CognitiveHealthSystem
    from core.goal_manager import GoalManager
    from core.knowledge_graph import KnowledgeGraph
    from core.knowledge_synthesis import KnowledgeSynthesisEngine
    from core.long_horizon_planner import LongHorizonPlanner

    goals = GoalManager(db_path=temp_db("goals"))
    horizon = LongHorizonPlanner(db_path=temp_db("horizon"), goals=goals)
    tree = horizon.build_planning_tree("Improve autonomous optimization")
    assert_true(tree["root"]["horizon"] == "long", "planning tree should create long horizon root")
    assert_true(horizon.snapshot()["nodes"], "horizon snapshot should expose nodes")

    memory = AdvancedMemorySystem(db_path=temp_db("memory"))
    graph = KnowledgeGraph(db_path=temp_db("graph"))
    graph.upsert_node("workflow:a", "workflow", "A", {})
    graph.upsert_node("task:a", "task", "A task", {})
    graph.connect("workflow:a", "task:a", "contains")
    synthesis = KnowledgeSynthesisEngine(db_path=temp_db("synthesis"), memory=memory, graph=graph)
    result = synthesis.synthesize("workflow optimization")
    assert_true(result["proposals"], "synthesis should produce improvement proposals")

    health = CognitiveHealthSystem(db_path=temp_db("health"))
    report = health.evaluate(
        {"graph": {"validation": {"valid": False}}, "society": {"agents": []}, "loop": {}},
        {"analysis": {"cognitive_quality": 0.3}},
    )
    assert_true(report["status"] == "critical", "low meta quality and graph inconsistency should be critical")


def test_meta_cognition_and_architecture_optimizer():
    from core.architecture_optimizer import ArchitectureOptimizer
    from core.meta_cognition import MetaCognitionEngine
    from core.strategy_manager import CognitiveStrategyManager

    strategies = CognitiveStrategyManager(db_path=temp_db("strategies"))
    meta = MetaCognitionEngine(db_path=temp_db("meta"), strategies=strategies)
    snapshot = {
        "loop": {"last_cycle": {"status": "completed", "duration_ms": 20}},
        "goals": {"total": 2, "status_counts": {"completed": 1}},
        "skills": {"skills": [{"score": 0.7}]},
        "graph": {"validation": {"valid": True}},
        "resources": {"pressure_score": 0.2},
        "society": {"agents": [{"reputation": 0.8}]},
        "simulations": [{"passed": True}],
    }
    observation = meta.observe_cognition(snapshot)
    proposal = meta.optimize_cognition(observation)
    assert_true(proposal["selected_strategy"], "meta-cognition should select an improved strategy")

    optimizer = ArchitectureOptimizer(db_path=temp_db("architecture"))
    benchmark = optimizer.benchmark_proposal(
        {"id": "proposal-test", "components": [{"component": "strategy"}], "rollback_plan": True, "tests": ["unit"]}
    )
    assert_true(benchmark["status"] in {"approved", "blocked"}, "architecture optimizer should gate proposal")


async def test_global_orchestration_and_meta_ui_snapshots():
    from core.orchestration_engine import AutonomousOrchestrationEngine
    from ui.cognitive_graph import CognitiveGraphView
    from ui.digital_twin_panel import DigitalTwinPanel
    from ui.evolution_view import AgentEvolutionView
    from ui.simulation_panel import SimulationUniversePanel
    from ui.strategy_dashboard import StrategyDashboard

    root = Path(tempfile.mkdtemp(prefix="jarvis_meta_orch_"))
    engine = AutonomousOrchestrationEngine(meta_config(root))
    await engine.handle_goal("Build a new coding workflow plugin", {"language": "python"}, execute=True)
    cycle = await engine.meta_cognitive_tick("coding workflow optimization")
    assert_true(cycle["meta"]["analysis"]["cognitive_quality"] >= 0, "meta cycle should score cognition")
    assert_true(cycle["twins"], "meta cycle should maintain digital twins")
    snapshot = engine.autonomy_snapshot()
    assert_true("meta_ecosystem" in snapshot, "autonomy snapshot should include meta ecosystem")

    assert_true(StrategyDashboard(engine).snapshot()["strategies"], "strategy dashboard should expose strategies")
    assert_true(DigitalTwinPanel(engine).snapshot()["twins"], "digital twin panel should expose twins")
    assert_true("runs" in SimulationUniversePanel(engine).snapshot(), "simulation panel should expose runs")
    assert_true("evolutionary_memory" in AgentEvolutionView(engine).snapshot(), "evolution view should expose memory")
    assert_true("meta_observations" in CognitiveGraphView(engine).snapshot(), "cognitive graph should expose meta observations")


async def main():
    tests = [
        test_strategy_marketplace_benchmarks_and_switching,
        test_digital_twins_simulate_failures,
        test_simulation_universe_concurrency_and_architecture_validation,
        test_self_stability_checkpoint_and_rollback,
        test_long_horizon_synthesis_and_cognitive_health,
        test_meta_cognition_and_architecture_optimizer,
        test_global_orchestration_and_meta_ui_snapshots,
    ]
    passed = 0
    for test in tests:
        if inspect.iscoroutinefunction(test):
            await test()
        else:
            test()
        passed += 1
        print(f"PASS {test.__name__}")
    print(f"\nMETA COGNITIVE ECOSYSTEM tests: {passed}/{len(tests)} passed")


if __name__ == "__main__":
    asyncio.run(main())
