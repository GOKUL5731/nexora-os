"""Self-healing, anomaly detection, and recovery coordination."""

from __future__ import annotations

from typing import Any

from core.module_manager import ModuleManager, get_module_manager


class SelfHealingEngine:
    """Detects unhealthy modules and attempts bounded, registered recovery."""

    def __init__(self, config: dict | None = None, modules: ModuleManager | None = None):
        self.config = config or {}
        self.modules = modules or get_module_manager()

    def detect_anomalies(self, health: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if health is None:
            module_map = {m["name"]: m for m in self.modules.list_modules()}
            failed = [m for m in module_map.values() if m.get("status") in {"failed", "error"}]
        else:
            failed = health.get("failed_modules", [])
        anomalies = []
        for module in failed:
            anomalies.append(
                {
                    "type": "module_failure",
                    "module": module.get("name", "unknown"),
                    "detail": module.get("error") or module.get("detail", ""),
                    "recoverable": True,
                }
            )
        return anomalies

    def recover(self, anomalies: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        anomalies = anomalies or self.detect_anomalies()
        results = []
        for anomaly in anomalies:
            if anomaly.get("type") != "module_failure":
                continue
            name = anomaly["module"]
            result = self.modules.restart(name)
            results.append({"module": name, **result})
        return results

    def self_heal_cycle(self, health: dict[str, Any] | None = None) -> dict[str, Any]:
        anomalies = self.detect_anomalies(health)
        recoveries = self.recover(anomalies)
        return {"anomalies": anomalies, "recoveries": recoveries, "stable": not anomalies or all(r.get("ok") for r in recoveries)}
