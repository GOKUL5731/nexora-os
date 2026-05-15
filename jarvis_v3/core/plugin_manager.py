"""
JARVIS Plugin System
Discovers, loads, validates, and manages plugins from the plugins/ directory.
Each plugin is a Python file with a register() function returning tool specs.
"""

import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("jarvis.plugins")

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugins"


class PluginSpec:
    """Describes a single plugin."""
    def __init__(self, name: str, version: str, description: str,
                 tools: list[str], author: str = "community", enabled: bool = True,
                 path: str = ""):
        self.name        = name
        self.version     = version
        self.description = description
        self.tools       = tools
        self.author      = author
        self.enabled     = enabled
        self.path        = path

    def to_dict(self):
        return {
            "name": self.name, "version": self.version,
            "description": self.description, "tools": self.tools,
            "author": self.author, "enabled": self.enabled, "path": self.path,
        }


class PluginManager:
    """Loads plugins and exposes their tools to the AgentRegistry."""

    def __init__(self, config: dict):
        self.config   = config
        self._plugins: dict[str, PluginSpec] = {}        # name → spec
        self._handlers: dict[str, Callable]  = {}        # tool → handler fn
        self._tool_plugins: dict[str, str] = {}
        self._state_file = PLUGIN_DIR / ".plugin_state.json"
        self._enabled_state = self._load_state()
        PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
        self._load_all()
        self._publish_state()

    # ── Discovery & loading ──────────────────────────────────────────────────
    def _load_all(self):
        for py_file in sorted(PLUGIN_DIR.glob("*.py")):
            if py_file.stem.startswith("_"):
                continue
            self._load_plugin(py_file)

    def _load_plugin(self, path: Path) -> bool:
        """Load a single plugin file. Returns True on success."""
        try:
            spec = importlib.util.spec_from_file_location(f"plugin_{path.stem}", path)
            mod  = importlib.util.module_from_spec(spec)
            sys.modules[f"plugin_{path.stem}"] = mod
            spec.loader.exec_module(mod)

            if not hasattr(mod, "register"):
                logger.warning(f"Plugin {path.name} has no register() function — skipped")
                return False

            registration: dict = mod.register(self.config)
            plugin_name = registration.get("name", path.stem)
            plugin_spec = PluginSpec(
                name        = plugin_name,
                version     = registration.get("version", "1.0.0"),
                description = registration.get("description", ""),
                tools       = list(registration.get("tools", {}).keys()),
                author      = registration.get("author", "community"),
                enabled     = self._enabled_state.get(plugin_name, True),
                path        = str(path),
            )

            # Register tool handlers
            if plugin_spec.enabled:
                for tool_name, handler in registration.get("tools", {}).items():
                    self._handlers[tool_name] = handler
                    self._tool_plugins[tool_name] = plugin_spec.name
                    logger.debug(f"  Tool registered: {tool_name}")

            self._plugins[plugin_spec.name] = plugin_spec
            self._publish_state()
            logger.info(f"✓ Plugin loaded: {plugin_spec.name} v{plugin_spec.version} ({len(plugin_spec.tools)} tools)")
            return True

        except Exception as e:
            logger.error(f"✗ Plugin load failed [{path.name}]: {e}")
            return False

    def reload_plugin(self, plugin_name: str) -> bool:
        """Hot-reload a plugin by name."""
        for py_file in PLUGIN_DIR.glob("*.py"):
            if py_file.stem == plugin_name or py_file.stem == plugin_name.replace(" ", "_").lower():
                # Remove old handlers
                spec = self._plugins.pop(plugin_name, None)
                if spec:
                    for tool in spec.tools:
                        self._handlers.pop(tool, None)
                        self._tool_plugins.pop(tool, None)
                return self._load_plugin(py_file)
        return False

    # ── Tool execution ───────────────────────────────────────────────────────
    async def execute(self, tool: str, args: dict) -> Any:
        handler = self._handlers.get(tool)
        if not handler:
            raise ValueError(f"PluginManager: no handler for tool '{tool}'")
        import asyncio, inspect
        if inspect.iscoroutinefunction(handler):
            return await handler(args)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: handler(args))

    # ── Registry API ─────────────────────────────────────────────────────────
    def list_tools(self) -> list[str]:
        return sorted(self._handlers.keys())

    def list_plugins(self) -> list[dict]:
        return [p.to_dict() for p in self._plugins.values()]

    def has_tool(self, tool: str) -> bool:
        return tool in self._handlers

    def enable(self, name: str) -> bool:
        if name in self._plugins:
            self._plugins[name].enabled = True
            self._enabled_state[name] = True
            self._save_state()
            ok = self.reload_plugin(name)
            self._publish_state()
            return ok
        return False

    def disable(self, name: str) -> bool:
        if name in self._plugins:
            self._plugins[name].enabled = False
            self._enabled_state[name] = False
            self._save_state()
            # Remove handlers
            for tool in self._plugins[name].tools:
                self._handlers.pop(tool, None)
                self._tool_plugins.pop(tool, None)
            self._publish_state()
            return True
        return False

    def reload_all(self) -> int:
        self._plugins.clear()
        self._handlers.clear()
        self._tool_plugins.clear()
        self._load_all()
        self._publish_state()
        return len(self._plugins)

    def _load_state(self) -> dict[str, bool]:
        try:
            if self._state_file.exists():
                return json.loads(self._state_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_state(self) -> None:
        try:
            self._state_file.write_text(json.dumps(self._enabled_state, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not save plugin state: %s", exc)

    def _publish_state(self) -> None:
        try:
            from core.event_bus import get_event_bus
            from core.module_manager import get_module_manager
            plugins = self.list_plugins()
            get_event_bus().set_state("plugins", plugins, source="plugin_manager")
            get_module_manager().register("plugin_manager", status="online", detail=f"{len(plugins)} plugins")
        except Exception:
            pass
