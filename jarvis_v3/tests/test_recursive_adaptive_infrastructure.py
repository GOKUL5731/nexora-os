"""Recursive adaptive intelligence infrastructure tests.

Run:
  python -X utf8 tests/test_recursive_adaptive_infrastructure.py
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
    root = Path(tempfile.mkdtemp(prefix="jarvis_recursive_"))
    return root / f"{name}.db"


def recursive_config(root: Path) -> dict:
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
        "ecosystem_memory": {"db_path": str(root / "ecosystem_memory.db")},
        "governance": {"db_path": str(root / "governance.db")},
        "observability": {"db_path": str(root / "observability.db")},
        "resource_intelligence": {"db_path": str(root / "resource_intelligence.db")},
        "distributed_cognition": {"db_path": str(root / "distributed_cognition.db")},
        "emergent_societies": {"db_path": str(root / "emergent_societies.db")},
        "adaptive_architecture": {"db_path": str(root / "adaptive_architecture.db")},
        "knowledge_discovery": {"db_path": str(root / "knowledge_discovery.db")},
        "orchestration_intelligence": {"db_path": str(root / "orchestration_intelligence.db")},
        "recursive_optimizer": {"db_path": str(root / "recursive_optimizer.db")},
    }


async def test_distributed_cognitive_network_concurrency():
    from core.distributed_cognition import DistributedCognitiveNetwork

    network = DistributedCognitiveNetwork(db_path=temp_db("distributed"))
    tasks = [{"task": f"optimize workflow {idx}", "context": {"idx": idx}} for idx in range(20)]
    results = await network.run_parallel(tasks, concurrency=6)
    assert_true(len(results) == 20, "distributed cognition should process all tasks")
    assert_true(all(r["route"] == network.DEFAULT_LAYERS for r in results), "every task should traverse all layers")
    assert_true(network.message_snapshot(), "layer messages should be observable")


def test_governance_enforcement_and_ecosystem_memory_consistency():
    from core.ecosystem_memory import EcosystemMemory
    from core.governance_engine import GovernanceEngine

    governance = GovernanceEngine(db_path=temp_db("governance"))
    blocked = governance.evaluate({"type": "architecture", "sandboxed": False, "benchmarked": False, "rollback_plan": False})
    assert_true(blocked["decision"] == "blocked", "unsafe proposal should be blocked")
    approved = governance.evaluate({"type": "architecture", "sandboxed": True, "benchmarked": True, "rollback_plan": True})
    assert_true(approved["decision"] == "approved", "safe proposal should pass governance")

    memory = EcosystemMemory(db_path=temp_db("ecosystem_memory"))
    memory.remember("strategic", "fast_path", {"strategy": "fast"}, score=0.8)
    memory.remember("simulation", "trial", {"passed": True}, score=0.9)
    report = memory.consistency_report()
    assert_true(report["ok"], "ecosystem memory scores should be consistent")
    assert_true(report["counts"]["strategic"] == 1, "strategic memory should be counted")


def test_resource_intelligence_reasoning_and_observability():
    from core.observability_engine import ObservabilityEngine
    from core.reasoning_strategy_engine import DynamicReasoningStrategyEngine
    from core.resource_intelligence import ResourceIntelligence

    resources = ResourceIntelligence(db_path=temp_db("resources"))
    decision = resources.optimize({"tasks": 5})
    benchmark = resources.benchmark([{"tasks": 1}, {"tasks": 10}])
    assert_true(decision["concurrency"] >= 1, "resource intelligence should choose usable concurrency")
    assert_true(benchmark["workloads"] == 2, "resource benchmark should include all workloads")

    reasoning = DynamicReasoningStrategyEngine()
    selected = reasoning.select("deep distributed architecture simulation", {"resource_pressure": 0.2, "confidence": 0.8, "latency_target_ms": 2000})
    assert_true(selected["mode"] in reasoning.MODES, "reasoning engine should select a valid mode")

    obs = ObservabilityEngine(db_path=temp_db("observability"))
    obs.record_metric("test.metric", 1.0)
    obs.record_trace("test.trace", {"ok": True}, 12.5)
    dashboard = obs.dashboard()
    assert_true("test.metric" in dashboard["latest_metrics"], "observability should expose latest metrics")
    assert_true(dashboard["traces"], "observability should expose traces")


def test_adaptive_architecture_and_recursive_optimizer_gates():
    from core.adaptive_architecture import AdaptiveArchitectureSystem
    from core.recursive_optimizer import RecursiveCognitiveOptimizer

    snapshot = {
        "loop": {"last_cycle": {"status": "completed", "duration_ms": 15}},
        "resources": {"pressure_score": 0.25, "cpu_percent": 10, "memory_percent": 40},
        "skills": {"skills": [{"score": 0.7}], "recommendations": []},
        "goals": {"total": 1, "status_counts": {"completed": 1}},
        "graph": {"opportunities": [], "validation": {"valid": True}},
        "meta_ecosystem": {"health": []},
    }
    architecture = AdaptiveArchitectureSystem(db_path=temp_db("adaptive_architecture"))
    evolved = architecture.evolve(snapshot)
    assert_true(evolved["selected"], "adaptive architecture should select a candidate")
    assert_true(evolved["selected"]["status"] in {"approved", "blocked"}, "candidate should be gated")

    optimizer = RecursiveCognitiveOptimizer(db_path=temp_db("recursive_optimizer"), architecture=architecture)
    cycle = optimizer.run_cycle(snapshot, "recursive optimization")
    assert_true(cycle["status"] in {"deployed", "simulated"}, "recursive cycle should be bounded")
    assert_true(optimizer.recent_cycles(), "recursive cycles should persist")


async def test_knowledge_discovery_orchestration_and_emergent_society():
    from core.collaboration_engine import CollaborationEngine
    from core.emergent_societies import EmergentSocietyEngine
    from core.knowledge_discovery import KnowledgeDiscoveryEngine
    from core.orchestration_intelligence import OrchestrationIntelligence
    from core.society_engine import AgentSocietyEngine

    discovery = KnowledgeDiscoveryEngine(db_path=temp_db("discovery"))
    found = await discovery.discover({"research": [], "graph": {"opportunities": []}, "skills": {"recommendations": []}}, limit=1)
    assert_true(found and "verification" in found[0], "knowledge discovery should research and verify gaps")

    orchestration = OrchestrationIntelligence(db_path=temp_db("orchestration"))
    schedule = orchestration.schedule(
        "optimize ecosystem",
        [
            {"id": "a", "title": "simulate architecture", "priority": 8, "target": "architecture"},
            {"id": "b", "title": "deploy architecture", "priority": 7, "target": "architecture"},
        ],
    )
    assert_true(schedule["schedule"]["tasks"][1]["status"] == "deferred", "conflicting lower priority task should defer")

    collab = CollaborationEngine(db_path=temp_db("collaboration"))
    society = AgentSocietyEngine(collaboration=collab, db_path=temp_db("society"))
    society.record_outcome("optimizer", "optimize planning optimize", True, quality=1.0)
    emergent = EmergentSocietyEngine(db_path=temp_db("emergent"), society=society)
    coalition = emergent.form_coalition("optimization push", ["optimize"])
    assert_true(coalition["agents"], "emergent society should form a coalition")


async def test_full_recursive_orchestration_and_ui_snapshots():
    from core.orchestration_engine import AutonomousOrchestrationEngine
    from ui.ecosystem_map import EcosystemMap
    from ui.evolution_graphs import EvolutionGraphs
    from ui.observability_dashboard import ObservabilityDashboard
    from ui.society_visualization import SocietyVisualization
    from ui.world_model_view import WorldModelView

    root = Path(tempfile.mkdtemp(prefix="jarvis_recursive_orch_"))
    engine = AutonomousOrchestrationEngine(recursive_config(root))
    await engine.handle_goal("Build an optimization workflow plugin", {"language": "python"}, execute=True)
    result = await engine.recursive_intelligence_tick("recursive infrastructure optimization")
    assert_true(result["recursive_optimization"]["evaluation"]["cognition_efficiency"] >= 0, "recursive tick should evaluate cognition")
    assert_true(result["distributed_cognition"]["route"], "recursive tick should run distributed cognition")
    snapshot = engine.autonomy_snapshot()
    recursive = snapshot["meta_ecosystem"]["recursive_infrastructure"]
    assert_true(recursive["recursive_cycles"], "snapshot should expose recursive cycles")
    assert_true(EcosystemMap(engine).snapshot()["title"] == "Ecosystem Map", "ecosystem map should render data")
    assert_true(SocietyVisualization(engine).snapshot()["coalitions"], "society visualization should show coalitions")
    assert_true(EvolutionGraphs(engine).snapshot()["cycles"], "evolution graphs should show cycles")
    assert_true(ObservabilityDashboard(engine).snapshot()["observability"], "observability dashboard should expose metrics")
    assert_true("nodes" in WorldModelView(engine).snapshot(), "world model view should expose graph nodes")


async def main():
    tests = [
        test_distributed_cognitive_network_concurrency,
        test_governance_enforcement_and_ecosystem_memory_consistency,
        test_resource_intelligence_reasoning_and_observability,
        test_adaptive_architecture_and_recursive_optimizer_gates,
        test_knowledge_discovery_orchestration_and_emergent_society,
        test_full_recursive_orchestration_and_ui_snapshots,
    ]
    passed = 0
    for test in tests:
        if inspect.iscoroutinefunction(test):
            await test()
        else:
            test()
        passed += 1
        print(f"PASS {test.__name__}")
    print(f"\nRECURSIVE ADAPTIVE INFRASTRUCTURE tests: {passed}/{len(tests)} passed")


if __name__ == "__main__":
    asyncio.run(main())
