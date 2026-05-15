"""JARVIS Web Agent — web search and URL fetching. Windows compatible."""

import asyncio
import logging
from agents.agent_registry import BaseAgent

logger = logging.getLogger("jarvis.agents.web")


class WebAgent(BaseAgent):
    def supported_tools(self):
        return ["web_search", "fetch_url", "download_file"]

    async def execute(self, tool: str, args: dict):
        if tool == "web_search":   return await self._search(args)
        if tool == "fetch_url":    return await self._fetch(args)
        if tool == "download_file":return await self._download(args)
        raise ValueError(f"WebAgent: unknown tool '{tool}'")

    async def _search(self, args: dict) -> dict:
        query = args.get("query", "")
        n     = args.get("num_results", 5)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._search_sync, query, n)

    def _search_sync(self, query: str, n: int) -> dict:
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=n):
                    results.append({
                        "title":   r.get("title", ""),
                        "url":     r.get("href", ""),
                        "snippet": r.get("body", "")[:400],
                    })
            logger.info(f"Web search '{query}': {len(results)} results")
            return {"query": query, "results": results, "count": len(results)}
        except ImportError:
            return {"error": "Install: pip install duckduckgo-search", "query": query, "results": []}
        except Exception as e:
            return {"error": str(e), "query": query, "results": []}

    async def _fetch(self, args: dict) -> dict:
        url = args.get("url", "")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync, url)

    def _fetch_sync(self, url: str) -> dict:
        try:
            import urllib.request
            from html.parser import HTMLParser

            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 JARVIS/2.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Simple HTML → text using stdlib (no BeautifulSoup needed)
            class _Strip(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self._parts = []
                    self._skip = False
                def handle_starttag(self, tag, attrs):
                    if tag in ("script", "style", "nav", "footer"):
                        self._skip = True
                def handle_endtag(self, tag):
                    if tag in ("script", "style", "nav", "footer"):
                        self._skip = False
                def handle_data(self, data):
                    if not self._skip and data.strip():
                        self._parts.append(data.strip())
                def text(self):
                    return "\n".join(self._parts[:200])

            parser = _Strip()
            parser.feed(html)
            return {"url": url, "content": parser.text(), "ok": True}

        except Exception as e:
            return {"url": url, "error": str(e), "ok": False}

    async def _download(self, args: dict) -> dict:
        import urllib.request
        from pathlib import Path

        url  = args.get("url", "")
        dest = Path(args.get("save_path", "downloads"))
        dest.mkdir(parents=True, exist_ok=True)

        filename = url.split("/")[-1].split("?")[0] or "download"
        out = dest / filename

        loop = asyncio.get_event_loop()
        def _dl():
            urllib.request.urlretrieve(url, out)
            return {"saved": str(out), "size": out.stat().st_size}
        return await loop.run_in_executor(None, _dl)
