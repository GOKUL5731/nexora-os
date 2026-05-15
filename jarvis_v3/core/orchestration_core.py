"""Global orchestration engine for the persistent digital cognitive ecosystem."""

from __future__ import annotations

from typing import Any

from core.architecture_optimizer import ArchitectureOptimizer
from core.adaptive_architecture import AdaptiveArchitectureSystem
from core.civilization_orchestrator import CivilizationOrchestrator
from core.cognitive_health import CognitiveHealthSystem
from core.digital_twin_engine import DigitalTwinEngine
from core.distributed_cognition import DistributedCognitiveNetwork
from core.ecosystem_memory import EcosystemMemory
from core.ecosystem_stability import EcosystemStabilityEngine
from core.emergent_societies import EmergentSocietyEngine
from core.evolutionary_memory import EvolutionaryMemory
from core.governance_engine import GovernanceEngine
from core.knowledge_discovery import KnowledgeDiscoveryEngine
from core.knowledge_synthesis import KnowledgeSynthesisEngine
from core.long_horizon_planner import LongHorizonPlanner
from core.memory_network import MultiLayerMemoryNetwork
from core.meta_cognition import MetaCognitionEngine
from core.observability_engine import ObservabilityEngine
from core.orchestration_intelligence import OrchestrationIntelligence
from core.reasoning_strategy_engine import DynamicReasoningStrategyEngine
from core.recursive_optimizer import RecursiveCognitiveOptimizer
from core.resource_intelligence import ResourceIntelligence
from core.self_stability_engine import SelfStabilityEngine
from core.simulation_universe import SimulationUniverse
from core.strategy_manager import CognitiveStrategyManager


class GlobalOrchestrationCore:
    """Coordinates meta-cognition, twins, strategies, simulations, memory, and health."""

    def __init__(self, config: dict | None = None, autonomy: Any = None):
        self.config = config or {}
        self.autonomy = autonomy
        self.strategies = CognitiveStrategyManager(self.config)
        self.dynamic_reasoning = DynamicReasoningStrategyEngine(self.config, self.strategies)
        self.twins = DigitalTwinEngine(self.config)
        self.evolutionary_memory = EvolutionaryMemory(self.config)
        self.ecosystem_memory = EcosystemMemory(self.config)
        self.memory_network = MultiLayerMemoryNetwork(
            self.config,
            memory=getattr(autonomy, "memory", None),
            evolutionary=self.evolutionary_memory,
        )
        self.stability = SelfStabilityEngine(self.config)
        self.governance = GovernanceEngine(self.config)
        self.universe = SimulationUniverse(
            self.config,
            simulation=getattr(autonomy, "simulation", None),
            twins=self.twins,
        )
        self.observability = ObservabilityEngine(self.config)
        self.resource_intelligence = ResourceIntelligence(self.config, resources=getattr(autonomy, "resources", None))
        self.distributed_cognition = DistributedCognitiveNetwork(self.config)
        self.emergent_societies = EmergentSocietyEngine(self.config, society=getattr(autonomy, "society", None))
        self.meta = MetaCognitionEngine(self.config, strategies=self.strategies)
        self.horizon = LongHorizonPlanner(self.config, goals=getattr(autonomy, "goals", None))
        self.synthesis = KnowledgeSynthesisEngine(
            self.config,
            memory=getattr(autonomy, "memory", None),
            graph=getattr(autonomy, "graph", None),
        )
        self.knowledge_discovery = KnowledgeDiscoveryEngine(
            self.config,
            research=getattr(autonomy, "research", None),
            synthesis=self.synthesis,
        )
        self.architecture = ArchitectureOptimizer(
            self.config,
            universe=self.universe,
            stability=self.stability,
            evolutionary_memory=self.evolutionary_memory,
        )
        self.adaptive_architecture = AdaptiveArchitectureSystem(
            self.config,
            universe=self.universe,
            stability=self.stability,
            governance=self.governance,
        )
        self.health = CognitiveHealthSystem(self.config)
        self.ecosystem_stability = EcosystemStabilityEngine(self.config, self.stability, self.governance)
        self.orchestration_intelligence = OrchestrationIntelligence(
            self.config,
            reasoning=self.dynamic_reasoning,
            resources=self.resource_intelligence,
        )
        self.recursive_optimizer = RecursiveCognitiveOptimizer(
            self.config,
            architecture=self.adaptive_architecture,
            stability=self.ecosystem_stability,
            governance=self.governance,
            strategies=self.dynamic_reasoning,
            memory=self.ecosystem_memory,
            observability=self.observability,
        )
        self.civilization = CivilizationOrchestrator(self.config, recursive_core=self)
        self._integrity_baseline = self.stability.record_integrity_snapshot(["core", "ui"])

    async def run_meta_cycle(self, topic: str = "autonomous cognitive ecosystem") -> dict[str, Any]:
        autonomy_snapshot = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        self.memory_network.record_sensory("autonomy_snapshot", autonomy_snapshot)
        self.twins.update_from_autonomy(autonomy_snapshot)
        twin_failures = self.twins.predict_failures()
        meta_observation = self.meta.observe_cognition(autonomy_snapshot)
        proposal = self.meta.optimize_cognition(meta_observation)
        synthesis = self.synthesis.synthesize(topic, {"meta": meta_observation})
        architecture = self.architecture.benchmark_proposal(
            self.architecture.propose(autonomy_snapshot, synthesis)
        )
        stability = self.stability.stability_gate(proposal)
        deployment = self.meta.deploy_improved_cognition(proposal, stability)
        health = self.health.evaluate(autonomy_snapshot, meta_observation, twin_failures)
        society_evolution = self.evolve_agent_society(autonomy_snapshot)
        self.memory_network.set_working("latest_meta_cycle", {"meta": meta_observation, "health": health})
        self.memory_network.remember_evolution(
            "meta_cycle",
            deployment["status"],
            {"score": meta_observation["analysis"]["cognitive_quality"]},
            {"proposal": proposal, "architecture": architecture, "health": health},
        )
        return {
            "meta": meta_observation,
            "proposal": proposal,
            "deployment": deployment,
            "twins": self.twins.list_twins(),
            "twin_failures": twin_failures,
            "strategy": self.strategies.active_strategy(),
            "synthesis": synthesis,
            "architecture": architecture,
            "health": health,
            "society_evolution": society_evolution,
            "stability": stability,
        }

    async def run_recursive_cycle(self, objective: str = "recursive adaptive intelligence") -> dict[str, Any]:
        autonomy_snapshot = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        self.observability.ingest_autonomy_snapshot(autonomy_snapshot)
        resource_decision = self.resource_intelligence.optimize({"objective": objective})
        reasoning = self.dynamic_reasoning.select(
            objective,
            {
                "resource_pressure": resource_decision["forecast"]["predicted_pressure"],
                "confidence": 0.7,
                "latency_target_ms": 1500,
            },
        )
        distributed = await self.distributed_cognition.run_pipeline(
            objective,
            {"strategy": reasoning, "resource_decision": resource_decision},
        )
        discoveries = await self.knowledge_discovery.discover(autonomy_snapshot, limit=2)
        society = self.emergent_societies.snapshot()
        if society["drift"]:
            self.emergent_societies.evolve_roles()
        coalition = self.emergent_societies.form_coalition(objective, ["optimize", "plan", "test"])
        orchestration = self.orchestration_intelligence.schedule(
            objective,
            [
                {"id": "discover", "title": "discover missing knowledge", "priority": 8, "target": "knowledge"},
                {"id": "simulate", "title": "simulate architecture candidate", "priority": 9, "target": "architecture"},
                {"id": "stabilize", "title": "validate ecosystem stability", "priority": 10, "target": "stability"},
            ],
            {"resource_pressure": resource_decision["forecast"]["predicted_pressure"]},
        )
        recursive = self.recursive_optimizer.run_cycle(autonomy_snapshot, objective)
        governance = self.governance.evaluate(
            {
                "type": "recursive_cycle",
                "sandboxed": True,
                "benchmarked": True,
                "rollback_plan": True,
                "objective": objective,
            },
            {"resource_pressure": resource_decision["forecast"]["predicted_pressure"]},
        )
        stability = self.ecosystem_stability.stabilize(autonomy_snapshot)
        self.ecosystem_memory.remember(
            "strategic",
            objective,
            {"reasoning": reasoning, "orchestration": orchestration, "recursive": recursive},
            score=recursive["evaluation"]["cognition_efficiency"],
            source="recursive_cycle",
        )
        return {
            "objective": objective,
            "resource_decision": resource_decision,
            "reasoning": reasoning,
            "distributed_cognition": distributed,
            "discoveries": discoveries,
            "coalition": coalition,
            "orchestration": orchestration,
            "recursive_optimization": recursive,
            "governance": governance,
            "stability": stability,
        }

    async def run_civilization_cycle(self, objective: str = "collective cognitive civilization") -> dict[str, Any]:
        autonomy_snapshot = self.autonomy.autonomy_snapshot() if self.autonomy else {}
        recursive_snapshot = self.snapshot()
        return await self.civilization.run_civilization_cycle(
            objective,
            {**autonomy_snapshot, "meta_ecosystem": recursive_snapshot},
        )

    def evolve_agent_society(self, autonomy_snapshot: dict[str, Any]) -> dict[str, Any]:
        society = autonomy_snapshot.get("society", {}).get("agents", [])
        changes = []
        if not self.autonomy or not hasattr(self.autonomy, "society"):
            return {"changes": changes}
        for agent in society:
            reputation = agent.get("reputation", 0.5)
            trust = agent.get("trust", 0.5)
            if reputation > 0.75 and trust > 0.7:
                changes.append({"agent": agent["agent"], "change": "increase hierarchy weight", "reason": "high reputation"})
            elif reputation < 0.4 or trust < 0.4:
                changes.append({"agent": agent["agent"], "change": "route through mentor agent", "reason": "low trust/reputation"})
        self.evolutionary_memory.record("agent_society_evolution", "primary_society", "planned", {"score": len(changes)}, {"changes": changes})
        return {"changes": changes}

    def coordinate(self, objective: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        strategy = self.strategies.choose_strategy(
            {
                "task": objective,
                "resource_pressure": context.get("resource_pressure", 0.0),
                "depth": context.get("depth"),
            }
        )
        tree = self.horizon.build_planning_tree(objective) if context.get("long_horizon") else {}
        scenarios = [
            {
                "type": "architecture",
                "scenario": {"components": [{"component": "strategy", "change": strategy["name"]}], "rollback_plan": True, "tests": ["strategy"]},
            }
        ]
        simulations = self.universe.run_batch(scenarios, concurrency=1)
        return {"strategy": strategy, "planning_tree": tree, "simulations": simulations}

    def snapshot(self) -> dict[str, Any]:
        return {
            "strategies": {
                "active": self.strategies.active_strategy(),
                "all": self.strategies.list_strategies(),
                "benchmarks": self.strategies.benchmark_history(limit=20),
            },
            "twins": self.twins.list_twins(limit=50),
            "simulation_universe": self.universe.recent_runs(limit=30),
            "long_horizon": self.horizon.snapshot(),
            "synthesis": self.synthesis.list_syntheses(limit=20),
            "health": self.health.recent_reports(limit=10),
            "stability": {
                "baseline": self._integrity_baseline,
                "latest_integrity": self.stability.verify_integrity(),
                "events": self.stability.recent_events(limit=20),
            },
            "evolutionary_memory": self.evolutionary_memory.timeline(limit=30),
            "memory_network": self.memory_network.snapshot(),
            "meta_observations": self.meta.recent_observations(limit=20),
            "recursive_infrastructure": {
                "recursive_cycles": self.recursive_optimizer.recent_cycles(limit=20),
                "adaptive_architecture": self.adaptive_architecture.recent_candidates(limit=20),
                "distributed_cognition": {
                    "runs": self.distributed_cognition.recent_runs(limit=20),
                    "messages": self.distributed_cognition.message_snapshot(limit=50),
                },
                "emergent_societies": self.emergent_societies.snapshot(),
                "resource_intelligence": self.resource_intelligence.history(limit=20),
                "governance": {
                    "policies": self.governance.policies(),
                    "decisions": self.governance.recent_decisions(limit=30),
                },
                "observability": self.observability.dashboard(limit=100),
                "ecosystem_memory": self.ecosystem_memory.snapshot(),
                "knowledge_discovery": self.knowledge_discovery.recent(limit=20),
                "orchestration_intelligence": self.orchestration_intelligence.recent(limit=20),
            },
            "civilization_layer": self.civilization.snapshot(),
        }
