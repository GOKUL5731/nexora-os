"""
JARVIS Phase 5 — Browser Automation Engine
Uses Playwright for headless/headed browser control:
- Form filling, clicking, scraping
- AI-guided navigation
- Screenshot + DOM capture
- Authenticated session management
"""
import asyncio, json, logging, re, time
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("jarvis.browser")
ROOT       = Path(__file__).resolve().parent.parent
SCREENSHOTS = ROOT / "screenshots" / "browser"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

_PLAYWRIGHT_OK = False
try:
    from playwright.async_api import async_playwright, Page, Browser
    _PLAYWRIGHT_OK = True
except ImportError:
    pass


class BrowserEngine:
    """
    Headless/headed browser automation via Playwright.
    Gracefully degrades to urllib fallback if Playwright unavailable.
    Install: pip install playwright && playwright install chromium
    """

    def __init__(self, config: dict = None, headless: bool = True):
        self.config   = config or {}
        self.headless = headless
        self._pw      = None
        self._browser: Optional[object] = None
        self._page:    Optional[object] = None
        self._context = None

    async def start(self) -> bool:
        """Launch browser. Returns True if Playwright available."""
        if not _PLAYWRIGHT_OK:
            logger.warning("[Browser] Playwright not installed. Run: pip install playwright && playwright install chromium")
            return False
        try:
            self._pw      = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            self._page = await self._context.new_page()
            logger.info("[Browser] Playwright browser started")
            return True
        except Exception as e:
            logger.error(f"[Browser] Failed to start: {e}")
            return False

    async def stop(self):
        try:
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass

    # ── Navigation ─────────────────────────────────────────────────────────────
    async def goto(self, url: str, wait_until: str = "networkidle") -> Dict:
        if not self._page:
            return await self._urllib_get(url)
        try:
            resp = await self._page.goto(url, wait_until=wait_until, timeout=20000)
            return {
                "url":    self._page.url,
                "status": resp.status if resp else 0,
                "title":  await self._page.title(),
                "ok":     True,
            }
        except Exception as e:
            return {"error": str(e), "ok": False}

    async def get_text(self) -> str:
        """Get visible page text."""
        if not self._page:
            return ""
        try:
            return await self._page.inner_text("body")
        except Exception:
            return ""

    async def get_html(self) -> str:
        if not self._page:
            return ""
        try:
            return await self._page.content()
        except Exception:
            return ""

    async def screenshot(self, name: str = None) -> Optional[Path]:
        if not self._page:
            return None
        try:
            ts   = name or f"browser_{int(time.time())}"
            dest = SCREENSHOTS / f"{ts}.png"
            await self._page.screenshot(path=str(dest), full_page=True)
            return dest
        except Exception as e:
            logger.error(f"[Browser] Screenshot failed: {e}")
            return None

    # ── Interaction ────────────────────────────────────────────────────────────
    async def click(self, selector: str) -> Dict:
        if not self._page:
            return {"error": "No page"}
        try:
            await self._page.click(selector, timeout=10000)
            return {"clicked": selector, "ok": True}
        except Exception as e:
            return {"error": str(e), "ok": False}

    async def fill(self, selector: str, value: str) -> Dict:
        if not self._page:
            return {"error": "No page"}
        try:
            await self._page.fill(selector, value, timeout=10000)
            return {"filled": selector, "value": value[:30], "ok": True}
        except Exception as e:
            return {"error": str(e), "ok": False}

    async def type_text(self, selector: str, text: str, delay: int = 50) -> Dict:
        if not self._page:
            return {"error": "No page"}
        try:
            await self._page.type(selector, text, delay=delay)
            return {"typed": True, "ok": True}
        except Exception as e:
            return {"error": str(e), "ok": False}

    async def press_key(self, key: str) -> Dict:
        if not self._page:
            return {"error": "No page"}
        try:
            await self._page.keyboard.press(key)
            return {"pressed": key, "ok": True}
        except Exception as e:
            return {"error": str(e), "ok": False}

    async def wait_for(self, selector: str, timeout: int = 10000) -> bool:
        if not self._page:
            return False
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    # ── Scraping ───────────────────────────────────────────────────────────────
    async def scrape_links(self) -> List[Dict]:
        if not self._page:
            return []
        try:
            links = await self._page.evaluate("""
                () => Array.from(document.querySelectorAll('a[href]'))
                    .map(a => ({text: a.innerText.trim().slice(0,80), href: a.href}))
                    .filter(l => l.href.startsWith('http'))
                    .slice(0, 50)
            """)
            return links
        except Exception:
            return []

    async def scrape_table(self, selector: str = "table") -> List[List[str]]:
        if not self._page:
            return []
        try:
            return await self._page.evaluate(f"""
                () => {{
                    const t = document.querySelector('{selector}');
                    if (!t) return [];
                    return Array.from(t.rows).map(r =>
                        Array.from(r.cells).map(c => c.innerText.trim())
                    );
                }}
            """)
        except Exception:
            return []

    async def extract_text_by_selector(self, selector: str) -> str:
        if not self._page:
            return ""
        try:
            return await self._page.inner_text(selector)
        except Exception:
            return ""

    # ── AI-Guided Navigation ───────────────────────────────────────────────────
    async def ai_navigate(self, task: str, orchestrator=None) -> Dict:
        """
        Use LLM to navigate a page toward a goal.
        Captures DOM structure, asks LLM what to do next, executes.
        """
        if not self._page:
            return {"error": "No browser page"}

        steps_taken = []
        for attempt in range(5):
            try:
                # Capture current state
                url   = self._page.url
                title = await self._page.title()
                # Get interactive elements
                elements = await self._page.evaluate("""
                    () => {
                        const els = [];
                        document.querySelectorAll('button,input,select,a,[role=button]').forEach((el,i) => {
                            if (i < 30) els.push({
                                tag:   el.tagName,
                                type:  el.type || '',
                                text:  (el.innerText || el.value || el.placeholder || '').trim().slice(0,50),
                                id:    el.id || '',
                                name:  el.name || ''
                            });
                        });
                        return els;
                    }
                """)

                if not orchestrator:
                    break

                prompt = (
                    f"Current page: {title} ({url})\n"
                    f"Task: {task}\n"
                    f"Interactive elements: {json.dumps(elements[:15])}\n\n"
                    f"What single action should I take? Respond as JSON:\n"
                    f"{{\"action\": \"click|fill|goto|done|fail\", \"selector\": \"...\", \"value\": \"...\", \"url\": \"...\", \"reason\": \"...\"}}"
                )
                resp = await orchestrator.process(prompt)
                raw  = resp.get("message", "{}")
                match = re.search(r'\{[\s\S]*\}', raw)
                if not match:
                    break
                action_spec = json.loads(match.group())
                action      = action_spec.get("action", "done")

                if action == "done":
                    break
                elif action == "fail":
                    return {"error": action_spec.get("reason", "AI navigation failed"), "steps": steps_taken}
                elif action == "click":
                    result = await self.click(action_spec.get("selector", ""))
                elif action == "fill":
                    result = await self.fill(action_spec.get("selector", ""), action_spec.get("value", ""))
                elif action == "goto":
                    result = await self.goto(action_spec.get("url", url))
                else:
                    break

                steps_taken.append({"attempt": attempt+1, "action": action_spec, "result": result})
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"[Browser] AI nav error at step {attempt}: {e}")
                break

        shot = await self.screenshot(f"ai_nav_{int(time.time())}")
        return {
            "task":      task,
            "steps":     steps_taken,
            "final_url": self._page.url,
            "screenshot": str(shot) if shot else None,
        }

    # ── Fallback (no Playwright) ───────────────────────────────────────────────
    async def _urllib_get(self, url: str) -> Dict:
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                body = r.read().decode("utf-8", errors="replace")
            # Strip HTML tags
            text = re.sub(r'<[^>]+>', ' ', body)
            text = re.sub(r'\s+', ' ', text).strip()
            return {"url": url, "text": text[:2000], "status": r.status, "ok": True, "method": "urllib"}
        except Exception as e:
            return {"error": str(e), "ok": False}

    # ── Convenience API ────────────────────────────────────────────────────────
    async def search_and_summarize(self, query: str, orchestrator=None) -> Dict:
        """Search DuckDuckGo and return summarized results."""
        search_url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
        nav = await self.goto(search_url)
        if not nav.get("ok"):
            return nav
        text = await self.get_text()
        links = await self.scrape_links()

        if orchestrator:
            summary_resp = await orchestrator.process(
                f"Summarize these search results for: '{query}'\n\n{text[:3000]}"
            )
            summary = summary_resp.get("message", text[:500])
        else:
            summary = text[:500]

        return {
            "query":   query,
            "links":   links[:10],
            "summary": summary,
            "ok":      True,
        }

    async def fill_form(self, fields: Dict[str, str], submit_selector: str = None) -> Dict:
        """Fill multiple form fields and optionally submit."""
        results = {}
        for selector, value in fields.items():
            results[selector] = await self.fill(selector, value)
        if submit_selector:
            results["submit"] = await self.click(submit_selector)
        return {"fields_filled": len(fields), "results": results, "ok": True}
