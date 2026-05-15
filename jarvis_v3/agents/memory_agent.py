"""JARVIS Memory Agent — exposes memory operations as tools."""
import logging
from agents.agent_registry import BaseAgent

logger = logging.getLogger("jarvis.agents.memory")


class MemoryAgent(BaseAgent):
    def __init__(self, config):
        super().__init__(config)
        self._mem = None

    def _get_mem(self):
        if not self._mem:
            from memory.memory_manager import MemoryManager
            self._mem = MemoryManager(self.config)
        return self._mem

    def supported_tools(self):
        return ["remember","search_memory","store_fact","get_user_profile","recall_skill"]

    async def execute(self, tool, args):
        m = self._get_mem()
        if tool == "remember":
            m.store_interaction(args.get("context",""), args.get("value",""), tags=args.get("tags",[]))
            return {"stored": True}
        if tool == "search_memory":
            return {"results": m.retrieve_relevant(args.get("query",""), args.get("limit",5))}
        if tool == "store_fact":
            m.store_fact(args["category"], args["key"], args["value"])
            return {"stored": True}
        if tool == "get_user_profile":
            return m.get_user_profile()
        if tool == "recall_skill":
            return m.recall_skill(args.get("name","")) or {"error": "Skill not found"}
        raise ValueError(f"MemoryAgent: unknown '{tool}'")
