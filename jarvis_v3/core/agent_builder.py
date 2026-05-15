"""
JARVIS Phase 3 — Agent Builder
Generates, tests, and registers new AI agents from natural language descriptions.
"""
import asyncio, json, logging, re, time
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger("jarvis.agent_builder")
ROOT    = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / "agents" / "generated"
AGENTS_DIR.mkdir(parents=True, exist_ok=True)

AGENT_TEMPLATE = '''"""
JARVIS Generated Agent: {name}
Description: {description}
Generated: {timestamp}
"""
import asyncio, logging
from typing import Dict

logger = logging.getLogger("jarvis.agent.{name}")

class {class_name}Agent:
    def __init__(self, config=None, orchestrator=None):
        self.name        = "{name}"
        self.type        = "{agent_type}"
        self.config      = config or {{}}
        self.orchestrator = orchestrator
        self.memory: Dict = {{}}

    async def execute(self, task: str, context: dict = None) -> Dict:
        logger.info(f"[{{self.name}}] Executing: {{task[:60]}}")
        {execute_body}

    async def _think(self, prompt: str) -> str:
        if self.orchestrator:
            resp = await self.orchestrator.process(prompt)
            return resp.get("message", "")
        return ""

# Register with agent manager
def register(manager):
    agent = {class_name}Agent(manager.config, manager.orchestrator)
    if hasattr(manager, "register_agent"):
        manager.register_agent(agent)
    else:
        manager._agents[agent.name] = agent
    logger.info(f"[AgentBuilder] Registered: {name}")
'''


class AgentBuilder:
    """
    Dynamically generates new agents from descriptions using LLM code generation.
    Validates, saves, and registers them into the AgentManager.
    """

    def __init__(self, orchestrator=None, agent_manager=None):
        self.orchestrator  = orchestrator
        self.agent_manager = agent_manager

    async def build_agent(self, description: str, agent_name: str = None) -> Dict:
        """
        Generate a new agent from a natural language description.
        Steps: describe → generate code → validate → save → register
        """
        name = (agent_name or re.sub(r'[^a-z0-9_]', '_',
                description.lower()[:30])).strip('_')
        class_name = ''.join(w.capitalize() for w in name.split('_'))
        timestamp  = time.strftime('%Y-%m-%d %H:%M:%S')

        logger.info(f"[AgentBuilder] Building agent: {name}")

        # Step 1: Generate execute body via LLM
        execute_body = await self._generate_execute_body(description)

        # Step 2: Fill template
        code = AGENT_TEMPLATE.format(
            name=name,
            class_name=class_name,
            description=description,
            agent_type="custom",
            timestamp=timestamp,
            execute_body=execute_body,
        )

        # Step 3: Syntax-check
        try:
            compile(code, f"{name}_agent.py", "exec")
        except SyntaxError as e:
            logger.error(f"[AgentBuilder] Syntax error in generated code: {e}")
            # Use safe fallback body
            execute_body = 'result = await self._think(f"Complete this task: {task}\\n\\nContext: {context}")\n        return {"result": result, "agent": self.name}'
            code = AGENT_TEMPLATE.format(
                name=name, class_name=class_name, description=description,
                agent_type="custom", timestamp=timestamp, execute_body=execute_body,
            )

        # Step 4: Save
        agent_file = AGENTS_DIR / f"{name}_agent.py"
        agent_file.write_text(code, encoding="utf-8")
        logger.info(f"[AgentBuilder] Saved: {agent_file}")

        # Step 5: Register
        registered = False
        if self.agent_manager:
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(f"agents.{name}", agent_file)
                mod  = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.register(self.agent_manager)
                registered = True
            except Exception as e:
                logger.error(f"[AgentBuilder] Registration failed: {e}")

        return {
            "name":       name,
            "class":      f"{class_name}Agent",
            "file":       str(agent_file),
            "registered": registered,
            "description": description,
        }

    async def _generate_execute_body(self, description: str) -> str:
        if not self.orchestrator:
            return ('result = await self._think(task)\n'
                    '        return {"result": result, "agent": self.name}')

        prompt = (
            f"Write ONLY the Python body of an async execute() method for an AI agent "
            f"that: {description}\n\n"
            f"Parameters available: task (str), context (dict), self.orchestrator, self._think(prompt)\n"
            f"Return a dict. Keep it under 20 lines. No def statement, no class wrapper.\n"
            f"Indent with 8 spaces (continuation of async def execute)."
        )
        body = await self.orchestrator.process(prompt)
        raw  = body.get("message", "")

        # Extract code block
        match = re.search(r'```python\n([\s\S]*?)```', raw)
        if match:
            raw = match.group(1)
        # Strip leading def lines
        lines = [l for l in raw.split('\n') if not l.strip().startswith('async def')]
        raw   = '\n'.join(lines).strip()

        if not raw:
            return ('result = await self._think(task)\n'
                    '        return {"result": result, "agent": self.name}')
        # Normalize indentation to 8 spaces
        normalized = '\n'.join('        ' + l.lstrip() for l in raw.split('\n') if l.strip())
        return normalized

    def list_generated_agents(self):
        return [f.stem.replace('_agent', '') for f in AGENTS_DIR.glob('*_agent.py')]

    def delete_agent(self, name: str) -> bool:
        f = AGENTS_DIR / f"{name}_agent.py"
        if f.exists():
            f.unlink()
            if self.agent_manager and name in self.agent_manager._agents:
                del self.agent_manager._agents[name]
            return True
        return False

    def get_agent_code(self, name: str) -> str:
        f = AGENTS_DIR / f"{name}_agent.py"
        return f.read_text(encoding="utf-8") if f.exists() else ""
