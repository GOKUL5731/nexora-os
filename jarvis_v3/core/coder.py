"""
JARVIS Coding Copilot — DeepSeek Coder powered.
Write, debug, refactor, explain, test, and generate plugins.
All code runs in sandboxed subprocesses.
"""

import asyncio
import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger("jarvis.coder")

CODER_SYSTEM = """You are JARVIS Coding Copilot powered by DeepSeek Coder.
You write clean, production-quality code.
Rules:
- Return ONLY code inside ```language blocks when writing code
- Be precise — no unnecessary explanations unless asked
- Prefer stdlib over third-party when possible
- Always handle errors gracefully
- Add docstrings to functions
- Windows-compatible code only
"""


class CodingCopilot:
    def __init__(self, config: dict, llm_router=None):
        self.config = config
        self.router = llm_router
        self._sandbox = Path(tempfile.gettempdir()) / "jarvis_sandbox"
        self._sandbox.mkdir(exist_ok=True)

    async def _ask_coder(self, prompt: str) -> str:
        if not self.router:
            from core.llm_client import LLMClient
            client = LLMClient(self.config)
            return await client.complete(prompt, system=CODER_SYSTEM,
                                         model=self.config["llm"].get("coder_model","deepseek-coder"))
        return await self.router.complete_async(
            prompt, system=CODER_SYSTEM, force_model="deepseek-coder"
        )

    # ── Extract code from LLM response ───────────────────────────────────────
    def _extract_code(self, text: str, lang: str = "python") -> str:
        patterns = [
            rf"```{lang}\s*(.*?)```",
            r"```\s*(.*?)```",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.DOTALL)
            if m:
                return m.group(1).strip()
        return text.strip()

    # ── Write code ────────────────────────────────────────────────────────────
    async def write(self, task: str, language: str = "python",
                    save_to: str = None) -> dict:
        prompt = f"Write a complete {language} program/function for:\n{task}\n\nReturn only code."
        raw    = await self._ask_coder(prompt)
        code   = self._extract_code(raw, language)

        result = {"code": code, "language": language}
        if save_to:
            Path(save_to).write_text(code, encoding="utf-8")
            result["saved"] = save_to
        return result

    # ── Run code in sandbox ───────────────────────────────────────────────────
    async def run(self, code: str, language: str = "python",
                  timeout: int = 30) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._run_sync, code, language, timeout
        )

    def _run_sync(self, code: str, language: str, timeout: int) -> dict:
        ext_map = {"python":"py","javascript":"js","powershell":"ps1","batch":"bat"}
        ext = ext_map.get(language.lower(), "py")
        cmd_map = {"python":[sys.executable], "javascript":["node"],
                   "powershell":["powershell","-File"]}
        cmd = cmd_map.get(language.lower(), [sys.executable])

        tmp = self._sandbox / f"run_temp.{ext}"
        tmp.write_text(code, encoding="utf-8")
        try:
            r = subprocess.run(
                cmd + [str(tmp)],
                capture_output=True, text=True, timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0,
            )
            return {
                "ok": r.returncode == 0,
                "stdout": r.stdout[:3000],
                "stderr": r.stderr[:1000],
                "returncode": r.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Timed out after {timeout}s"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Debug (run → fix → rerun) ─────────────────────────────────────────────
    async def debug(self, code: str, language: str = "python") -> dict:
        result = await self.run(code, language)
        if result.get("ok"):
            return {"ok": True, "message": "Code ran successfully", "result": result}

        error = result.get("stderr") or result.get("error","Unknown error")
        fix_prompt = (
            f"This {language} code has an error. Fix it.\n\n"
            f"Code:\n```{language}\n{code}\n```\n\n"
            f"Error:\n{error}\n\n"
            f"Return ONLY the fixed code."
        )
        raw_fix  = await self._ask_coder(fix_prompt)
        fixed    = self._extract_code(raw_fix, language)
        rerun    = await self.run(fixed, language)

        return {
            "ok": rerun.get("ok", False),
            "original_error": error[:500],
            "fixed_code": fixed,
            "rerun": rerun,
        }

    # ── Explain code ──────────────────────────────────────────────────────────
    async def explain(self, code: str) -> dict:
        raw = await self._ask_coder(
            f"Explain this code clearly and concisely:\n```\n{code}\n```"
        )
        return {"explanation": raw.strip()}

    # ── Refactor ──────────────────────────────────────────────────────────────
    async def refactor(self, code: str, goal: str = "improve readability") -> dict:
        raw = await self._ask_coder(
            f"Refactor this code to {goal}. Return only the improved code.\n```\n{code}\n```"
        )
        return {"refactored": self._extract_code(raw), "goal": goal}

    # ── Generate tests ────────────────────────────────────────────────────────
    async def generate_tests(self, code: str) -> dict:
        raw = await self._ask_coder(
            f"Write pytest unit tests for this code:\n```python\n{code}\n```\n"
            f"Return only the test file."
        )
        tests = self._extract_code(raw, "python")
        return {"tests": tests}

    # ── Generate JARVIS plugin ────────────────────────────────────────────────
    async def generate_plugin(self, description: str) -> dict:
        """Ask DeepSeek Coder to write a new JARVIS plugin file."""
        prompt = (
            f"Write a JARVIS plugin Python file for: {description}\n\n"
            f"The plugin must follow this exact structure:\n"
            f"```python\n"
            f"def register(config: dict) -> dict:\n"
            f"    def my_tool(args: dict) -> dict:\n"
            f"        # implementation\n"
            f"        return {{\"result\": ...}}\n\n"
            f"    return {{\n"
            f"        \"name\": \"Plugin Name\",\n"
            f"        \"version\": \"1.0.0\",\n"
            f"        \"description\": \"...\",\n"
            f"        \"author\": \"jarvis-coder\",\n"
            f"        \"tools\": {{\"tool_name\": my_tool}},\n"
            f"    }}\n"
            f"```\n\n"
            f"Return ONLY the complete plugin file."
        )
        raw  = await self._ask_coder(prompt)
        code = self._extract_code(raw, "python")

        # Validate syntax
        tmp = self._sandbox / "plugin_test.py"
        tmp.write_text(code, encoding="utf-8")
        check = subprocess.run(
            [sys.executable, "-m", "py_compile", str(tmp)],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0,
        )
        syntax_ok = check.returncode == 0

        return {
            "ok": syntax_ok,
            "code": code,
            "syntax_error": check.stderr.strip() if not syntax_ok else None,
            "description": description,
        }

    async def save_plugin(self, code: str, name: str) -> dict:
        """Save a generated plugin to the plugins/ directory."""
        safe_name = re.sub(r"[^\w]", "_", name.lower()) + "_plugin.py"
        dest = Path("plugins") / safe_name
        dest.write_text(code, encoding="utf-8")
        return {"saved": str(dest), "name": safe_name}
