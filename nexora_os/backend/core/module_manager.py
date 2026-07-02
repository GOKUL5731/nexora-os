from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

from .event_bus import EventBus


@dataclass(slots=True)
class ModuleState:
    name: str
    status: str
    detail: str = ""
    updated_at: float = 0.0


class ModuleManager:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._modules: dict[str, ModuleState] = {}

    def register(self, name: str, status: str = "online", detail: str = "") -> None:
        self._modules[name] = ModuleState(name, status, detail, time.time())
        self._sync()

    def update(self, name: str, status: str, detail: str = "") -> None:
        self.register(name, status, detail)

    def list(self) -> list[dict[str, Any]]:
        return [asdict(row) for row in self._modules.values()]

    def _sync(self) -> None:
        self.bus.set_state("modules", self.list(), "module_manager")
