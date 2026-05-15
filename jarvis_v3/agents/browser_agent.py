"""JARVIS Browser Agent — separate file (was embedded in code_agent.py)."""
import asyncio, logging
from pathlib import Path
from agents.agent_registry import BaseAgent

logger = logging.getLogger("jarvis.agents.browser")


class BrowserAgent(BaseAgent):
    def __init__(self, config):
        super().__init__(config)
        self._browser = self._page = None

    def supported_tools(self):
        return ["browser_navigate","browser_click","browser_fill",
                "browser_text","browser_screenshot","browser_close",
                "browser_open_url"]

    async def execute(self, tool, args):
        if tool == "browser_navigate":   return await self._nav(args)
        if tool == "browser_open_url":   return await self._nav(args)
        if tool == "browser_click":      return await self._click(args)
        if tool == "browser_fill":       return await self._fill(args)
        if tool == "browser_text":       return await self._text(args)
        if tool == "browser_screenshot": return await self._ss(args)
        if tool == "browser_close":      return await self._close(args)
        raise ValueError(f"BrowserAgent: unknown '{tool}'")

    async def _get_page(self):
        if self._page:
            return self._page
        try:
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            self._browser = await pw.chromium.launch(headless=False)
            self._page = await self._browser.new_page()
            return self._page
        except ImportError:
            raise ImportError("pip install playwright && python -m playwright install chromium")

    async def _nav(self, args):
        url = args.get("url", args.get("query", "https://google.com"))
        if not url.startswith("http"):
            url = f"https://www.google.com/search?q={url.replace(' ','+')}"
        import subprocess, sys
        try:
            subprocess.Popen(["start", url], shell=True)
            return {"opened": url}
        except Exception:
            pass
        p = await self._get_page()
        await p.goto(url, wait_until="domcontentloaded", timeout=20000)
        return {"url": url, "title": await p.title()}

    async def _click(self, args):
        p = await self._get_page()
        if args.get("text"):
            await p.get_by_text(args["text"]).first.click()
        else:
            await p.click(args.get("selector",""))
        return {"clicked": args.get("text") or args.get("selector")}

    async def _fill(self, args):
        p = await self._get_page()
        for sel, val in args.get("fields", {}).items():
            await p.fill(sel, str(val))
        if args.get("submit"):
            await p.keyboard.press("Enter")
        return {"filled": list(args.get("fields",{}).keys())}

    async def _text(self, args):
        p = await self._get_page()
        text = await p.inner_text("body")
        return {"text": text[:4000], "url": p.url}

    async def _ss(self, args):
        p = await self._get_page()
        out = args.get("path","screenshots/browser.png")
        Path(out).parent.mkdir(exist_ok=True)
        await p.screenshot(path=out)
        return {"saved": out}

    async def _close(self, args):
        if self._browser:
            await self._browser.close()
            self._browser = self._page = None
        return {"status": "closed"}
