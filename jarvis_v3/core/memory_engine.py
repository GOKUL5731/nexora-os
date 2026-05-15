"""
Compatibility layer for the JARVIS memory subsystem.

The production memory implementation lives in memory.memory_manager and now
includes long-term interactions, episodic events, preferences, error/solution
memory, and local SQLite vector memory.
"""

from memory.memory_manager import MemoryManager as MemoryEngine
from memory.memory_manager import MemoryManager

__all__ = ["MemoryEngine", "MemoryManager"]
