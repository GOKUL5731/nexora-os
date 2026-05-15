"""Collective cognitive civilization layer tests.

Run:
  python -X utf8 tests/test_cognitive_civilization_layer.py
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
    root = Path(tempfile.mkdtemp(prefix="jarvis_civilization_"))
    return root / f"{name}.db"


def civilization_config(root: Path) -> dict:
    names = [
        "planning", "collaboration", "workflow_generator", "prediction", "reflection", "evolution",
        "advanced_memory", "knowledge_graph", "goals", "simulation", "society", "skill_evolution",
        "research", "personality_adaptation", "strategies", "digital_twins", "meta_cognition",
        "simulation_universe", "long_horizon", "knowledge_synthesis", "architecture_optimizer",
        "cognitive_health", "self_stability", "evolutionary_memory", "ecosystem_memory",
        "governance", "observability", "resource_intelligence", "distributed_cognition",
        "emergent_societies", "adaptive_architecture", "knowledge_discovery",
        "orchestration_intelligence", "recursive_optimizer", "collective_memory",
        "cognitive_culture", "cognitive_economy", "adaptive_ontology", "civilizations",
        "collective_cognition", "scientific_discovery", "distributed_research",
        "strategic_forecasting", "ecosystem_governance", "ecosystem_health",
    ]
    cfg = {name: {"db_path": str(root / f"{name}.db")} for name in names}
    cfg["reflection"]["slow_ms"] = 1_000_000
    return cfg


async def test_collective_cognitive_network_federation():
    from core.collective_cognition import CollectiveCognitiveNetwork
    from core.collective_memory_engine import CollectiveMemoryEngine

    memory = CollectiveMemoryEngine(db_path=temp_db("collective_memory"))
    network = CollectiveCognitiveNetwork(db_path=temp_db("collective_cognition"), memory=memory)
    network.ensure_default_clusters()
    result = await network.federated_reason("optimize plugin architecture", ["coding", "research"])
    assert_true(len(result["results"]) == 2, "federation should run selected clusters")
    assert_true(memory.recall("collective", "federation"), "federation result should sync into collective memory")


def test_civilization_memory_culture_economy_and_ontology():
    from core.adaptive_ontology import AdaptiveOntologyEngine
    from core.civilization_engine import CivilizationEngine
    from core.cognitive_culture import CognitiveCultureSystem
    from core.cognitive_economy import CognitiveEconomy
    from core.collective_memory_engine import CollectiveMemoryEngine

    memory = CollectiveMemoryEngine(db_path=temp_db("collective_memory"))
    culture = CognitiveCultureSystem(db_path=temp_db("culture"))
    economy = CognitiveEconomy(db_path=temp_db("economy"))
    civs = CivilizationEngine(db_path=temp_db("civilizations"), memory=memory, culture=culture, economy=economy)
    evolved = civs.evolve("research", {"success_rate": 0.9, "innovation_score": 0.8, "new_specialization": "hypothesis_agent", "contribution": 5, "efficiency": 0.85})
    assert_true(evolved["generation"] >= 2, "high innovation should advance civilization generation")
    ranked = culture.compare_cultures("research architecture discovery")
    assert_true(ranked[0]["selection_score"] >= ranked[-1]["selection_score"], "cultures should rank by objective fit")
    economy.exchange("research", "optimization", "knowledge_module", 3.0)
    assert_true(economy.recent_exchanges(), "economy should record exchanges")
    assert_true(memory.consistency_report()["ok"], "collective memory should be consistent")

    ontology = AdaptiveOntologyEngine(db_path=temp_db("ontology"))
    ontology.evolve_from_sources([{"name": "test", "type": "capability", "terms": ["workflow synthesis", "civilization governance"]}])
    assert_true(not ontology.missing_capabilities(["workflow synthesis"]), "known capability should not be missing")


def test_scientific_discovery_governance_health_and_forecasting():
    from core.ecosystem_governance import EcosystemGovernanceSystem
    from core.ecosystem_health import EcosystemHealthEngine
    from core.scientific_discovery import ScientificDiscoveryEngine
    from core.strategic_forecasting import StrategicForecastingEngine

    snapshot = {
        "graph": {"opportunities": [{"target": "workflow:a", "type": "bottleneck"}]},
        "skills": {"recommendations": []},
        "resources": {"pressure_score": 0.2},
        "civilizations": {"civilizations": [{"name": "research", "health": 0.8}]},
        "collective_memory": {"consistency": {"ok": True}},
        "research": {"runs": [{"id": "r1"}]},
        "governance": {"decisions": []},
    }
    science = ScientificDiscoveryEngine(db_path=temp_db("science"))
    discoveries = science.run_discovery(snapshot, limit=1)
    assert_true(discoveries[0]["conclusion"]["confidence"] > 0, "scientific discovery should produce confidence")

    governance = EcosystemGovernanceSystem(db_path=temp_db("egov"))
    competition = governance.evaluate_competition(
        [
            {"name": "safe", "target_type": "architecture", "score": 0.8, "sandboxed": True, "benchmarked": True, "rollback_plan": True},
            {"name": "unsafe", "target_type": "architecture", "score": 0.95, "sandboxed": False, "benchmarked": False, "rollback_plan": False},
        ]
    )
    assert_true(competition["winner"]["name"] == "safe", "governance should prefer safe candidate over unsafe high score")

    health = EcosystemHealthEngine(db_path=temp_db("health"))
    report = health.evaluate(snapshot)
    assert_true(report["score"] > 0.5, "healthy civilization snapshot should score above degraded range")

    forecast = StrategicForecastingEngine(db_path=temp_db("forecast")).forecast("civilization optimization", snapshot, 60)
    assert_true(forecast["recommended_priorities"], "forecast should recommend priorities")


async def test_distributed_research_network_parallel_labs():
    from core.distributed_research import DistributedResearchNetwork

    network = DistributedResearchNetwork(db_path=temp_db("distributed_research"))
    runs = await network.run_parallel_research(
        "reasoning culture optimization",
        {"graph": {"opportunities": []}, "skills": {"recommendations": []}, "resources": {"pressure_score": 0.1}},
        labs=["architecture_lab", "reasoning_lab"],
    )
    assert_true(len(runs) == 2, "distributed research should run requested labs")
    assert_true(network.recent_runs(), "research runs should persist")


async def test_full_civilization_orchestration_and_ui_snapshots():
    from core.orchestration_engine import AutonomousOrchestrationEngine
    from ui.civilization_dashboard import CivilizationDashboard
    from ui.collective_memory_map import CollectiveMemoryMap
    from ui.governance_dashboard import GovernanceDashboard
    from ui.research_network_view import ResearchNetworkView
    from ui.strategic_timeline import StrategicTimeline

    root = Path(tempfile.mkdtemp(prefix="jarvis_civilization_orch_"))
    engine = AutonomousOrchestrationEngine(civilization_config(root))
    await engine.handle_goal("Build a research optimization plugin", {"language": "python"}, execute=True)
    result = await engine.civilization_tick("civilization-scale optimization")
    assert_true(result["federation"]["results"], "civilization tick should federate cognition")
    assert_true(result["health"]["score"] >= 0, "civilization tick should evaluate health")
    snapshot = engine.autonomy_snapshot()
    layer = snapshot["meta_ecosystem"]["civilization_layer"]
    assert_true(layer["civilizations"]["civilizations"], "snapshot should expose civilizations")

    assert_true(CivilizationDashboard(engine).snapshot()["civilizations"], "civilization dashboard should expose civilizations")
    assert_true(CollectiveMemoryMap(engine).snapshot()["nodes"], "collective memory map should expose memory nodes")
    assert_true(ResearchNetworkView(engine).snapshot()["labs"], "research network view should expose labs")
    assert_true("health" in GovernanceDashboard(engine).snapshot(), "governance dashboard should expose health")
    assert_true(StrategicTimeline(engine).snapshot()["timeline"], "strategic timeline should expose timeline items")


async def main():
    tests = [
        test_collective_cognitive_network_federation,
        test_civilization_memory_culture_economy_and_ontology,
        test_scientific_discovery_governance_health_and_forecasting,
        test_distributed_research_network_parallel_labs,
        test_full_civilization_orchestration_and_ui_snapshots,
    ]
    passed = 0
    for test in tests:
        if inspect.iscoroutinefunction(test):
            await test()
        else:
            test()
        passed += 1
        print(f"PASS {test.__name__}")
    print(f"\nCOGNITIVE CIVILIZATION tests: {passed}/{len(tests)} passed")


if __name__ == "__main__":
    asyncio.run(main())
