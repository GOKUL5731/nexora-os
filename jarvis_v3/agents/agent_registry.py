"""
JARVIS Agent Registry — safe lazy loading + plugin support.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("jarvis.agents")


class BaseAgent(ABC):
    def __init__(self, config: dict):
        self.config = config

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def supported_tools(self) -> list[str]: ...

    @abstractmethod
    async def execute(self, tool: str, args: dict) -> Any: ...


class AgentRegistry:
    def __init__(self, config: dict):
        self.config = config
        self._agents: dict[str, BaseAgent]  = {}
        self._tool_map: dict[str, str]       = {}
        self._plugin_mgr = None
        self._load_agents()
        self._load_plugins()

    def _load_agents(self):
        agent_classes = [
            ("agents.web_agent",    "WebAgent"),
            ("agents.system_agent", "SystemAgent"),
            ("agents.code_agent",   "CodeAgent"),
            ("agents.voice_agent",  "VoiceAgent"),
            ("agents.vision_agent", "VisionAgent"),
            ("agents.browser_agent","BrowserAgent"),
            ("agents.memory_agent", "MemoryAgent"),
        ]
        for module_path, class_name in agent_classes:
            try:
                import importlib
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                agent = cls(self.config)
                self._agents[agent.name] = agent
                for tool in agent.supported_tools():
                    self._tool_map[tool] = agent.name
                logger.info(f"✓ {agent.name}")
            except Exception as e:
                logger.warning(f"✗ {class_name}: {e}")
        logger.info(f"Tools available: {len(self._tool_map)}")

    def _load_plugins(self):
        try:
            from core.plugin_manager import PluginManager
            self.attach_plugins(PluginManager(self.config))
        except Exception as e:
            logger.warning(f"Plugins unavailable: {e}")

    def attach_plugins(self, plugin_mgr):
        """Wire plugin manager so its tools are reachable."""
        self._plugin_mgr = plugin_mgr
        for tool in plugin_mgr.list_tools():
            self._tool_map[f"plugin:{tool}"] = "__plugin__"
            self._tool_map[tool] = "__plugin__"  # also without prefix
        logger.info(f"Plugin tools registered: {plugin_mgr.list_tools()}")

    def get_agent(self, tool: str) -> BaseAgent:
        agent_name = self._tool_map.get(tool)
        if not agent_name:
            raise ValueError(f"No agent handles '{tool}'. Available: {list(self._tool_map.keys())[:15]}")
        if agent_name == "__plugin__" and self._plugin_mgr:
            return _PluginProxy(self._plugin_mgr)
        return self._agents[agent_name]

    def list_tools(self) -> list[str]:
        return sorted(self._tool_map.keys())

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())


class _PluginProxy:
    """Thin proxy so plugins work with the execute(tool, args) interface."""
    def __init__(self, plugin_mgr):
        self._mgr = plugin_mgr

    async def execute(self, tool: str, args: dict) -> Any:
        return await self._mgr.execute(tool, args)
