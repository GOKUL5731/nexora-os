"""JARVIS Code Agent — write, run, and debug code. Windows safe."""
import asyncio, logging, subprocess, sys, tempfile
from pathlib import Path
from agents.agent_registry import BaseAgent

logger = logging.getLogger("jarvis.agents.code")

LANG = {
    "python":     {"ext": ".py",  "cmd": [sys.executable]},
    "javascript": {"ext": ".js",  "cmd": ["node"]},
    "js":         {"ext": ".js",  "cmd": ["node"]},
    "powershell": {"ext": ".ps1", "cmd": ["powershell", "-File"]},
    "batch":      {"ext": ".bat", "cmd": []},
    "bash":       {"ext": ".sh",  "cmd": ["bash"]},
}

class CodeAgent(BaseAgent):
    def supported_tools(self):
        return ["run_code", "write_code", "debug_code", "explain_code"]

    async def execute(self, tool, args):
        if tool == "run_code":     return await self._run(args)
        if tool == "write_code":   return await self._write(args)
        if tool == "debug_code":   return await self._debug(args)
        if tool == "explain_code": return await self._explain(args)
        raise ValueError(f"CodeAgent: unknown '{tool}'")

    async def _run(self, args):
        code = args.get("code", "")
        lang = args.get("language", "python").lower()
        cfg  = LANG.get(lang)
        if not cfg:
            return {"error": f"Unsupported language: {lang}"}

        with tempfile.NamedTemporaryFile(suffix=cfg["ext"], mode="w",
                                         encoding="utf-8", delete=False) as f:
            f.write(code)
            tmp = f.name
        try:
            cmd = cfg["cmd"] + [tmp] if cfg["cmd"] else [tmp]
            loop = asyncio.get_event_loop()
            def _exec():
                r = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=args.get("timeout", 30),
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0
                )
                return {"returncode": r.returncode, "stdout": r.stdout[:3000],
                        "stderr": r.stderr[:1000], "ok": r.returncode == 0}
            return await loop.run_in_executor(None, _exec)
        except subprocess.TimeoutExpired:
            return {"error": "Timed out"}
        finally:
            Path(tmp).unlink(missing_ok=True)

    async def _write(self, args):
        p = Path(args["path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(args.get("code", ""), encoding="utf-8")
        return {"written": str(p)}

    async def _debug(self, args):
        result = await self._run(args)
        if result.get("ok"):
            return result
        from core.llm_client import LLMClient
        llm = LLMClient(self.config)
        fix = await llm.complete(
            f"Fix this code error:\n\nCode:\n{args.get('code','')}\n\nError:\n{result.get('stderr','')}\n\nReturn ONLY fixed code."
        )
        fix = fix.strip().replace("```python","").replace("```","").strip()
        rerun = await self._run({**args, "code": fix})
        return {"fixed_code": fix, "rerun": rerun, "original_error": result.get("stderr","")}

    async def _explain(self, args):
        from core.llm_client import LLMClient
        llm = LLMClient(self.config)
        exp = await llm.complete(f"Explain this code clearly:\n\n{args.get('code','')}")
        return {"explanation": exp}


# ─────────────────────────────────────────────────────────────────────────────
"""JARVIS Browser Agent — Playwright. Falls back gracefully if not installed."""
import asyncio, logging
from agents.agent_registry import BaseAgent

logger = logging.getLogger("jarvis.agents.browser")

class BrowserAgent(BaseAgent):
    def __init__(self, config):
        super().__init__(config)
        self._browser = None
        self._page    = None

    def supported_tools(self):
        return ["browser_navigate", "browser_click", "browser_fill", "browser_text",
                "browser_screenshot", "browser_close"]

    async def execute(self, tool, args):
        if tool == "browser_navigate":   return await self._nav(args)
        if tool == "browser_click":      return await self._click(args)
        if tool == "browser_fill":       return await self._fill(args)
        if tool == "browser_text":       return await self._text(args)
        if tool == "browser_screenshot": return await self._ss(args)
        if tool == "browser_close":      return await self._close(args)
        raise ValueError(f"BrowserAgent: unknown '{tool}'")

    async def _page_(self):
        if self._page:
            return self._page
        try:
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            self._browser = await pw.chromium.launch(headless=False)
            self._page = await self._browser.new_page()
            return self._page
        except ImportError:
            raise ImportError("Install: pip install playwright && python -m playwright install chromium")

    async def _nav(self, args):
        p = await self._page_()
        await p.goto(args["url"], wait_until="domcontentloaded", timeout=20000)
        return {"url": args["url"], "title": await p.title()}

    async def _click(self, args):
        p = await self._page_()
        if args.get("text"):
            await p.get_by_text(args["text"]).first.click()
        else:
            await p.click(args.get("selector",""))
        return {"clicked": args.get("text") or args.get("selector")}

    async def _fill(self, args):
        p = await self._page_()
        for sel, val in args.get("fields", {}).items():
            await p.fill(sel, str(val))
        if args.get("submit"):
            await p.keyboard.press("Enter")
        return {"filled": list(args.get("fields", {}).keys())}

    async def _text(self, args):
        p = await self._page_()
        text = await p.inner_text("body")
        return {"text": text[:4000], "url": p.url}

    async def _ss(self, args):
        p = await self._page_()
        out = args.get("path", "screenshots/browser.png")
        Path(out).parent.mkdir(exist_ok=True)
        await p.screenshot(path=out)
        return {"saved": out}

    async def _close(self, args):
        if self._browser:
            await self._browser.close()
            self._browser = self._page = None
        return {"status": "closed"}


# ─────────────────────────────────────────────────────────────────────────────
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
        return ["remember", "search_memory", "store_fact", "get_user_profile", "recall_skill"]

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
