from __future__ import annotations

import time
from typing import Any


class ContextManager:
    """
    Build unified context awareness with relevance scoring and token budgeting.
    """
    def __init__(self, memory_engine: Any) -> None:
        self.memory = memory_engine
        self.max_tokens = 4000

    def build_context(self, request: str, source: str, raw_context: dict[str, Any]) -> dict[str, Any]:
        memories = self.memory.search(request, 10) if self.memory else []
        # Score and deduplicate
        seen_ids = set()
        deduped = []
        for mem in memories:
            if mem.get('id') not in seen_ids:
                seen_ids.add(mem.get('id'))
                deduped.append(mem)

        # In a real system, apply token compression here
        # For now, return top 5
        final_memories = deduped[:5]

        permissions = raw_context.get('permissions', {})

        return {
            "request": request,
            "conversation_messages": raw_context.get("conversation_messages", []),
            "conversation_history": raw_context.get("conversation_history", ""),
            "cognitive": raw_context.get("cognitive", {}),
            "source": source,
            "timestamp": time.time(),
            "relevant_memories": final_memories,
            "active_application": raw_context.get('active_application', ''),
            "active_window": raw_context.get('active_window', ''),
            "clipboard": raw_context.get('clipboard', '') if permissions.get('clipboard', False) else None,
            "visible_screen": raw_context.get('visible_screen', '') if permissions.get('screen', False) else None,
            "available_tools": raw_context.get('available_tools', []),
            "system_health": raw_context.get('system_health', 'online')
        }
