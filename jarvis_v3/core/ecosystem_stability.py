"""Self-stabilizing ecosystem controls for recursive adaptive intelligence."""

from __future__ import annotations

from typing import Any

from core.governance_engine import GovernanceEngine
from core.self_stability_engine import SelfStabilityEngine


class EcosystemStabilityEngine:
    """Detects instability and coordinates isolation, rollback, and integrity restoration."""

    def __init__(
        self,
        config: dict | None = None,
        stability: SelfStabilityEngine | None = None,
        governance: GovernanceEngine | None = None,
    ):
        self.config = config or {}
        self.stability = stability or SelfStabilityEngine(self.config)
        self.governance = governance or GovernanceEngine(self.config)

    def detect(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        issues = []
        health = snapshot.get("meta_ecosystem", {}).get("health", [])
        latest_health = health[0] if health else {}
        if latest_health.get("status") == "critical":
            issues.append({"type": "cognitive_health_critical", "severity": "high"})
        graph = snapshot.get("graph", {}).get("validation", {})
        if graph and not graph.get("valid", True):
            issues.append({"type": "graph_integrity", "severity": "high"})
        memory = snapshot.get("meta_ecosystem", {}).get("memory_network", {})
        consistency = memory.get("evolutionary", {}).get("status_counts", {}) if isinstance(memory.get("evolutionary"), dict) else {}
        if consistency.get("blocked", 0) > 5:
            issues.append({"type": "evolution_blocking", "severity": "medium"})
        resources = snapshot.get("resources", {})
        if resources.get("pressure_score", 0) > 0.9:
            issues.append({"type": "resource_overload", "severity": "high"})
        return issues

    def isolate(self, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        actions = []
        for issue in issues:
            if issue["type"] == "resource_overload":
                actions.append({"action": "reduce concurrency to one and unload idle models", "issue": issue})
            elif issue["type"] == "graph_integrity":
                actions.append({"action": "pause graph-dependent autonomous deployment", "issue": issue})
            elif issue["type"] == "cognitive_health_critical":
                actions.append({"action": "switch to conservative strategy and require manual confirmation for deployment", "issue": issue})
            else:
                actions.append({"action": "quarantine unstable evolution proposal", "issue": issue})
        return actions

    def stabilize(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        issues = self.detect(snapshot)
        isolation = self.isolate(issues)
        integrity = self.stability.verify_integrity()
        decision = self.governance.evaluate(
            {
                "type": "stability_recovery",
                "sandboxed": True,
                "benchmarked": True,
                "rollback_plan": True,
                "actions": isolation,
            },
            {"resource_pressure": snapshot.get("resources", {}).get("pressure_score", 0.0)},
        )
        return {
            "stable": not issues and integrity["ok"] and decision["decision"] == "approved",
            "issues": issues,
            "isolation": isolation,
            "integrity": integrity,
            "governance": decision,
        }
