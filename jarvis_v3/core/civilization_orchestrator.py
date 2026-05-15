"""Top-level orchestration for the self-evolving cognitive civilization layer."""

from __future__ import annotations

from typing import Any

from core.adaptive_ontology import AdaptiveOntologyEngine
from core.civilization_engine import CivilizationEngine
from core.cognitive_culture import CognitiveCultureSystem
from core.cognitive_economy import CognitiveEconomy
from core.collective_cognition import CollectiveCognitiveNetwork
from core.collective_memory_engine import CollectiveMemoryEngine
from core.distributed_research import DistributedResearchNetwork
from core.ecosystem_governance import EcosystemGovernanceSystem
from core.ecosystem_health import EcosystemHealthEngine
from core.scientific_discovery import ScientificDiscoveryEngine
from core.strategic_forecasting import StrategicForecastingEngine


class CivilizationOrchestrator:
    """Coordinates civilizations, collective cognition, research, economy, governance, and health."""

    def __init__(self, config: dict | None = None, recursive_core: Any = None):
        self.config = config or {}
        self.recursive_core = recursive_core
        self.collective_memory = CollectiveMemoryEngine(self.config)
        self.culture = CognitiveCultureSystem(self.config)
        self.economy = CognitiveEconomy(self.config)
        self.civilizations = CivilizationEngine(
            self.config,
            memory=self.collective_memory,
            culture=self.culture,
            economy=self.economy,
        )
        self.collective_cognition = CollectiveCognitiveNetwork(self.config, memory=self.collective_memory)
        self.science = ScientificDiscoveryEngine(
            self.config,
            universe=getattr(recursive_core, "universe", None),
            memory=self.collective_memory,
        )
        self.research_network = DistributedResearchNetwork(self.config, discovery=self.science)
        self.forecasting = StrategicForecastingEngine(self.config)
        self.governance = EcosystemGovernanceSystem(self.config, governance=getattr(recursive_core, "governance", None))
        self.health = EcosystemHealthEngine(self.config)
        self.ontology = AdaptiveOntologyEngine(self.config)

    async def run_civilization_cycle(self, objective: str, base_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        base_snapshot = base_snapshot or {}
        self.collective_cognition.ensure_default_clusters()
        federation = await self.collective_cognition.federated_reason(objective)
        discoveries = self.science.run_discovery(base_snapshot, limit=2)
        research = await self.research_network.run_parallel_research(objective, base_snapshot, labs=["architecture_lab", "optimization_lab"])
        for civ in self.civilizations.list_civilizations():
            self.civilizations.evolve(
                civ["name"],
                {
                    "success_rate": 0.72,
                    "innovation_score": 0.65 + (0.1 if civ["name"] == "research" else 0),
                    "contribution": 2.0,
                    "efficiency": 0.7,
                },
            )
        self.economy.exchange("research", "optimization", "knowledge_module", 5.0, {"objective": objective})
        self.ontology.evolve_from_sources(
            [
                {"name": "civilization_cycle", "type": "strategy", "terms": [objective, "collective cognition", "governance"]},
                {"name": "research", "type": "scientific", "terms": [d["topic"] for d in discoveries]},
            ]
        )
        snapshot = self.snapshot(include_health=False)
        forecast = self.forecasting.forecast(objective, snapshot, horizon_days=90)
        competition = self.governance.evaluate_competition(
            [
                {"name": civ["name"], "target_type": "civilization", "score": civ["health"], "sandboxed": True, "benchmarked": True, "rollback_plan": True}
                for civ in self.civilizations.list_civilizations()
            ]
        )
        health = self.health.evaluate({**snapshot, "governance": {"decisions": self.governance.recent()}})
        self.collective_memory.remember(
            "strategic",
            "federation",
            objective,
            {"forecast": forecast, "competition": competition, "health": health},
            confidence=health["score"],
            contributors=[c["name"] for c in self.civilizations.list_civilizations()],
        )
        return {
            "objective": objective,
            "federation": federation,
            "discoveries": discoveries,
            "research": research,
            "forecast": forecast,
            "competition": competition,
            "health": health,
            "ontology": self.ontology.snapshot(),
        }

    def snapshot(self, include_health: bool = True) -> dict[str, Any]:
        data = {
            "civilizations": self.civilizations.snapshot(),
            "collective_cognition": self.collective_cognition.snapshot(),
            "collective_memory": self.collective_memory.snapshot(),
            "culture": self.culture.snapshot(),
            "economy": self.economy.snapshot(),
            "research": self.research_network.snapshot(),
            "scientific_discovery": self.science.recent(),
            "forecasts": self.forecasting.recent(),
            "governance": {"decisions": self.governance.recent()},
            "ontology": self.ontology.snapshot(),
        }
        if include_health:
            data["health"] = self.health.recent()
        return data
