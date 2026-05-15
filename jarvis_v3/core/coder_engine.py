"""Compatibility layer for the DeepSeek Coder powered coding engine."""

from core.coder import CodingCopilot as CoderEngine
from core.coder import CodingCopilot

__all__ = ["CoderEngine", "CodingCopilot"]
