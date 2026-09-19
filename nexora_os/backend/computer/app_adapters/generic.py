from __future__ import annotations

import abc
from typing import Any

class ApplicationAdapter(abc.ABC):
    """
    Interface for integrating external AI applications (Codex, Cursor, Antigravity)
    and standard Windows applications.
    """
    
    @abc.abstractmethod
    def discover(self) -> dict[str, Any]:
        """Detects if the application is installed and available."""
        pass

    @abc.abstractmethod
    async def launch(self, workspace_path: str = "") -> dict[str, Any]:
        """Launches the application, optionally attached to a workspace."""
        pass

    @abc.abstractmethod
    async def attach(self, window_id: str) -> bool:
        """Attaches to an existing running window of this application."""
        pass

    @abc.abstractmethod
    async def send_prompt(self, prompt: str) -> dict[str, Any]:
        """Sends an AI prompt or instruction to the application's interface."""
        pass

    @abc.abstractmethod
    async def observe_output(self) -> dict[str, Any]:
        """Reads the current state, output, or diffs from the application."""
        pass

    @abc.abstractmethod
    def detect_waiting(self) -> bool:
        """Detects if the agent/application is waiting for user input."""
        pass

    @abc.abstractmethod
    def detect_completion(self) -> bool:
        """Detects if the agent/application has finished its current task."""
        pass

    @abc.abstractmethod
    async def close(self) -> bool:
        """Closes the application."""
        pass
