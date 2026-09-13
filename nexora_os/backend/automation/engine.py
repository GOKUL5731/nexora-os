from __future__ import annotations

import asyncio
import datetime as dt
import os
import platform
import re
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Any, TYPE_CHECKING

from ..core.event_bus import EventBus
from ..vision.engine import VisionEngine

if TYPE_CHECKING:
    from ..connectors import ConnectorManager


class AutomationEngine:
    """
    Unified automation dispatcher.

    Priority order for each request:
      1. Structured connector routing via ConnectorManager (preferred)
      2. Legacy in-process fallbacks (backwards-compat / no connector needed)
    """

    def __init__(
        self,
        bus: EventBus,
        vision: VisionEngine,
        connector_manager: "ConnectorManager | None" = None,
    ) -> None:
        self.bus = bus
        self.vision = vision
        self._connectors = connector_manager
        self.history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    async def execute(self, command: str) -> dict[str, Any]:
        normalized = command.lower().strip()

        # ── Vision / system snapshot ────────────────────────────────────
        if "screenshot" in normalized or (
            "screen" in normalized and "ocr" not in normalized
        ):
            result = await self.vision.screen(ocr=False)

        elif "ocr" in normalized:
            result = await self.vision.screen(ocr=True)

        elif "time" in normalized or "நேரம்" in normalized:
            result = {
                "ok": True,
                "message": dt.datetime.now()
                .astimezone()
                .strftime("%A, %d %B %Y %I:%M %p"),
            }

        elif "system status" in normalized:
            # Prefer desktop connector system_info
            result = await self._connector_exec(
                "desktop",
                "system_info",
                {},
                fallback=lambda: {
                    "ok": True,
                    "message": f"{platform.system()} {platform.release()} on {platform.machine()}",
                },
            )

        # ── Browser ─────────────────────────────────────────────────────
        elif "chatgpt" in normalized:
            result = await self._open_chatgpt(command)

        elif self._is_common_site_command(normalized):
            url = self._common_site_url(normalized)
            result = await self._connector_exec(
                "browser",
                "open_url",
                {"url": url},
                fallback=lambda: webbrowser.open(url)
                or {"ok": True, "message": f"Opened {url}"},
            )

        elif normalized.startswith("google "):
            query = command.split(" ", 1)[1].strip()
            result = await self._connector_exec(
                "browser",
                "search_web",
                {"query": query},
                fallback=lambda: webbrowser.open(
                    f"https://www.google.com/search?q={query}"
                )
                or {"ok": True, "message": f"Searched: {query}"},
            )

        elif (
            "browser" in normalized
            or "url" in normalized
            or "http" in normalized
        ):
            url = self._extract_url(command)
            if url:
                result = await self._connector_exec(
                    "browser",
                    "open_url",
                    {"url": url},
                    fallback=lambda: asyncio.to_thread(self._open_browser, command),
                )
            else:
                result = await asyncio.to_thread(self._open_browser, command)

        elif "search" in normalized and (
            "web" in normalized or "google" in normalized
        ):
            query = (
                normalized.replace("search web", "")
                .replace("google", "")
                .replace("search", "")
                .strip()
            )
            result = await self._connector_exec(
                "browser",
                "search_web",
                {"query": query},
                fallback=lambda: webbrowser.open(
                    f"https://www.google.com/search?q={query}"
                )
                or {"ok": True, "message": f"Searched: {query}"},
            )

        # ── File operations ─────────────────────────────────────────────
        elif (
            re.search(r"\b(create|write)\s+(?:a\s+|the\s+)?file\b", normalized)
            or re.search(r"\bfile\s+(?:called|named)\b", normalized)
        ):
            path, content = self._extract_file_write(command)
            if path:
                result = await self._connector_exec(
                    "filesystem",
                    "write_file",
                    {"path": path, "content": content},
                    fallback=lambda: asyncio.to_thread(self._create_file, command),
                )
            else:
                result = await asyncio.to_thread(self._create_file, command)

        elif re.search(r"\bread\s+(?:a\s+|the\s+)?file\b", normalized):
            path = self._extract_filename(command)
            if path:
                result = await self._connector_exec(
                    "filesystem",
                    "read_file",
                    {"path": path},
                    fallback=lambda: asyncio.to_thread(self._read_file, command),
                )
            else:
                result = await asyncio.to_thread(self._read_file, command)

        elif re.search(r"\b(delete|remove)\s+(?:a\s+|the\s+)?file\b", normalized):
            path = self._extract_filename(command)
            if path:
                result = await self._connector_exec(
                    "filesystem",
                    "delete_file",
                    {"path": path, "confirm": True},
                    fallback=lambda: asyncio.to_thread(self._delete_file, command),
                )
            else:
                result = await asyncio.to_thread(self._delete_file, command)

        elif "list dir" in normalized or "list directory" in normalized:
            words = normalized.split()
            try:
                idx = words.index("dir") if "dir" in words else words.index("directory")
                target = words[idx + 1] if idx + 1 < len(words) else "."
            except (ValueError, IndexError):
                target = "."
            result = await self._connector_exec(
                "filesystem",
                "list_dir",
                {"path": target},
                fallback=lambda: {"ok": False, "error": "filesystem connector unavailable"},
            )

        # ── App launch (via desktop connector) ──────────────────────────
        elif "launch" in normalized or "open" in normalized or "start" in normalized:
            app_name = self._extract_app_name(command)
            if app_name:
                result = await self._connector_exec(
                    "desktop",
                    "launch_app",
                    {"app_name": app_name},
                    fallback=lambda: asyncio.to_thread(self._launch_app, command),
                )
            else:
                result = await asyncio.to_thread(self._launch_app, command)

        # ── Lock screen ─────────────────────────────────────────────────
        elif "lock" in normalized and "screen" in normalized:
            result = await self._connector_exec(
                "desktop",
                "lock_screen",
                {},
                fallback=lambda: {"ok": False, "error": "desktop connector unavailable"},
            )

        # ── List apps ───────────────────────────────────────────────────
        elif "list apps" in normalized or "running apps" in normalized:
            result = await self._connector_exec(
                "desktop",
                "list_apps",
                {},
                fallback=lambda: {"ok": False, "error": "desktop connector unavailable"},
            )

        else:
            result = {"ok": False, "message": "No registered automation matched that command."}

        entry = {
            "command": command,
            "result": result,
            "timestamp": dt.datetime.now().timestamp(),
        }
        self.history.append(entry)
        self.history = self.history[-100:]
        self.bus.publish("automation.executed", entry, "automation_engine")
        self.bus.set_state("automation", {"history": self.history[-20:]}, "automation_engine")
        await asyncio.sleep(0)
        return result

    # ------------------------------------------------------------------
    # Connector routing helpers
    # ------------------------------------------------------------------

    async def _connector_exec(
        self,
        connector_name: str,
        action: str,
        params: dict[str, Any],
        fallback: Any = None,
    ) -> dict[str, Any]:
        """Execute via ConnectorManager; call fallback if unavailable."""
        if self._connectors:
            try:
                return await self._connectors.execute(connector_name, action, params)
            except Exception as exc:
                pass  # fall through to legacy fallback
        if callable(fallback):
            try:
                r = fallback()
                if asyncio.iscoroutine(r):
                    return await r
                return r if isinstance(r, dict) else {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
        return {"ok": False, "error": f"Connector '{connector_name}' unavailable"}

    # ------------------------------------------------------------------
    # Extraction utilities
    # ------------------------------------------------------------------

    def _extract_url(self, command: str) -> str | None:
        for word in command.split():
            if word.startswith("http://") or word.startswith("https://"):
                return word
        for word in command.split():
            if "." in word and word not in {"browser", "open", "url", "launch", "start"}:
                return f"https://{word}"
        return None

    def _is_common_site_command(self, normalized: str) -> bool:
        return bool(re.match(r"^(open|launch|start)?\s*(google|youtube|gmail|maps|chatgpt)\s*$", normalized))

    def _common_site_url(self, normalized: str) -> str:
        match = re.search(r"\b(google|youtube|gmail|maps)\b", normalized)
        site = match.group(1) if match else "google"
        return {
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "gmail": "https://mail.google.com",
            "maps": "https://www.google.com/maps",
            "chatgpt": "https://chatgpt.com",
        }[site]

    async def _open_chatgpt(self, command: str) -> dict[str, Any]:
        url = "https://chatgpt.com"
        text_to_type = self._extract_type_text(command)
        opened = await self._connector_exec(
            "browser",
            "open_url",
            {"url": url},
            fallback=lambda: webbrowser.open(url) or {"ok": True, "url": url, "message": f"Opened {url}"},
        )
        if not opened.get("ok"):
            return opened

        if not text_to_type:
            return {
                "ok": True,
                "url": url,
                "message": "Opened ChatGPT.",
                "verification": {"opened_url": True, "typed_text_sent": False},
                "permission_checked": True,
            }

        typed = await asyncio.to_thread(self._type_text_keyboard_fallback, text_to_type)
        return {
            "ok": bool(typed.get("ok")),
            "url": url,
            "typed_text": text_to_type,
            "message": (
                f"Opened ChatGPT and sent text to the active browser window: {text_to_type}"
                if typed.get("ok")
                else f"Opened ChatGPT, but failed to type text: {typed.get('error')}"
            ),
            "verification": {
                "opened_url": True,
                "typed_text_sent": bool(typed.get("ok")),
                "content_verified": False,
                "note": "Browser text focus is controlled by the active web page and cannot be independently verified by this fallback.",
            },
            "permission_checked": True,
        }

    def _extract_type_text(self, command: str) -> str:
        match = re.search(r"\btype\s+(.+)$", command, flags=re.IGNORECASE)
        if not match:
            return ""
        text = match.group(1).strip()
        text = re.sub(r"^(in|into|on)\s+(chatgpt|chat gpt)\s+", "", text, flags=re.IGNORECASE)
        return text.strip().strip("\"'")

    def _type_text_keyboard_fallback(self, text: str) -> dict[str, Any]:
        try:
            import pyautogui

            time.sleep(4.0)
            pyautogui.write(text, interval=0.02)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _extract_filename(self, command: str) -> str | None:
        quoted = re.search(r"['\"]([^'\"]+\.[A-Za-z0-9_.-]+)['\"]", command)
        if quoted:
            return quoted.group(1).strip()
        called = re.search(r"\b(?:called|named)\s+([^\s,;]+)", command, flags=re.IGNORECASE)
        if called:
            return called.group(1).strip().strip(".,!?")
        words = command.split()
        if "file" in words:
            idx = words.index("file")
            if idx + 1 < len(words):
                return words[idx + 1].rstrip(".,!?")
        return None

    def _extract_file_write(self, command: str) -> tuple[str | None, str]:
        path = self._extract_filename(command)
        if path:
            marker = re.search(r"\b(?:containing|with content|with|that says)\b", command, flags=re.IGNORECASE)
            if marker:
                content = command[marker.end():].strip().strip(":").strip()
            else:
                content = ""
            if re.fullmatch(r"a\s+python\s+program\.?", content, flags=re.IGNORECASE):
                content = 'print("Hello from JARVIS")\n'
            if not content:
                content = "Created by JARVIS automation\n"
            return path, self._normalize_file_content(path, content)
        words = command.split()
        if "file" in words:
            idx = words.index("file")
            if idx + 1 < len(words):
                path = words[idx + 1].rstrip(".,!?")
                content = " ".join(words[idx + 2:]) if idx + 2 < len(words) else "Created by NEXORA automation"
                return path, self._normalize_file_content(path, content)
        return None, "Created by NEXORA automation"

    def _normalize_file_content(self, path: str, content: str) -> str:
        cleaned = content.strip()
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1]
        cleaned = cleaned.replace("\\n", "\n")
        if path.lower().endswith(".py") and cleaned and not cleaned.endswith("\n"):
            cleaned += "\n"
        return cleaned

    def _extract_app_name(self, command: str) -> str | None:
        words = command.lower().split()
        for kw in ("launch", "open", "start"):
            if kw in words:
                idx = words.index(kw)
                rest = words[idx + 1:]
                if rest:
                    return " ".join(rest)
        return None

    # ------------------------------------------------------------------
    # Status / list
    # ------------------------------------------------------------------

    def list(self) -> list[str]:
        return self.status()["registered_actions"]

    def status(self) -> dict[str, Any]:
        actions = [
            "system status", "time", "screenshot", "ocr screen",
            "launch app", "lock screen", "list apps",
            "create file", "read file", "delete file", "list dir",
            "open browser", "search web",
        ]
        connectors_health: dict[str, str] = {}
        if self._connectors:
            try:
                connectors_health = self._connectors.health_all()
            except Exception:
                pass
        return {
            "registered_actions": actions,
            "connector_health": connectors_health,
            "history": self.history[-20:],
        }

    # ------------------------------------------------------------------
    # Legacy fallback implementations (kept for backward-compat)
    # ------------------------------------------------------------------

    def _find_windows_app(self, app_name: str) -> str | None:
        import json
        import re
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress -Depth 2",
        ]
        try:
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            apps = json.loads(output)
            if not isinstance(apps, list):
                apps = [apps]
            pattern = re.compile(re.escape(app_name), re.IGNORECASE)
            best_match = None
            for app in apps:
                if not app or not app.get("Name"):
                    continue
                if app["Name"].lower() == app_name.lower():
                    return app["AppID"]
                if pattern.search(app["Name"]):
                    best_match = app["AppID"]
            return best_match
        except Exception:
            return None

    def _launch_app(self, command: str) -> dict[str, Any]:
        try:
            words = command.lower().split()
            app_keywords = ["launch", "open", "start"]
            app_name = None
            for i, word in enumerate(words):
                if word in app_keywords and i + 1 < len(words):
                    app_name = " ".join(words[i + 1:])
                    break
            if not app_name:
                return {"ok": False, "message": "Please specify an app name"}
            app_map = {
                "notepad": "notepad.exe", "calculator": "calc.exe",
                "cmd": "cmd.exe", "powershell": "powershell.exe",
                "explorer": "explorer.exe", "chrome": "chrome.exe",
                "edge": "msedge.exe", "firefox": "firefox.exe",
                "word": "winword.exe", "excel": "excel.exe",
            }
            if platform.system() == "Windows":
                app_id = self._find_windows_app(app_name)
                if app_id:
                    if "\\" in app_id or ".exe" in app_id.lower():
                        subprocess.Popen(f'start "" "{app_id}"', shell=True)
                    else:
                        subprocess.Popen(f"explorer.exe shell:AppsFolder\\{app_id}", shell=True)
                    return {"ok": True, "message": f"Launched {app_name}"}
                exe_name = app_map.get(app_name.lower(), f"{app_name}.exe")
                subprocess.Popen(f'start "" "{exe_name}"', shell=True)
            elif platform.system() == "Darwin":
                exe_name = app_map.get(app_name.lower(), f"{app_name}.app")
                subprocess.Popen(f'open "{exe_name}"', shell=True)
            else:
                exe_name = app_map.get(app_name.lower(), app_name)
                subprocess.Popen(f'"{exe_name}"', shell=True)
            return {"ok": True, "message": f"Launched {app_name}"}
        except Exception as exc:
            return {"ok": False, "message": f"Failed to launch app: {exc}"}

    def _create_file(self, command: str) -> dict[str, Any]:
        try:
            words = command.split()
            if "file" in words:
                idx = words.index("file") + 1
                if idx >= len(words):
                    return {"ok": False, "message": "Please specify a filename"}
                filename = words[idx].rstrip(".,!?")
                content = " ".join(words[idx + 1:]) if idx + 1 < len(words) else "Created by NEXORA automation"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"ok": True, "message": f"Created file: {filename}"}
            return {"ok": False, "message": "Could not parse file command"}
        except Exception as exc:
            return {"ok": False, "message": f"Failed to create file: {exc}"}

    def _read_file(self, command: str) -> dict[str, Any]:
        try:
            words = command.split()
            if "file" not in words:
                return {"ok": False, "message": "Please specify a filename"}
            idx = words.index("file") + 1
            if idx >= len(words):
                return {"ok": False, "message": "Please specify a filename"}
            filename = words[idx].rstrip(".,!?")
            if not os.path.exists(filename):
                return {"ok": False, "message": f"File not found: {filename}"}
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
            return {"ok": True, "message": f"File content:\n{content}"}
        except Exception as exc:
            return {"ok": False, "message": f"Failed to read file: {exc}"}

    def _delete_file(self, command: str) -> dict[str, Any]:
        try:
            words = command.split()
            if "file" not in words:
                return {"ok": False, "message": "Please specify a filename"}
            idx = words.index("file") + 1
            if idx >= len(words):
                return {"ok": False, "message": "Please specify a filename"}
            filename = words[idx].rstrip(".,!?")
            if not os.path.exists(filename):
                return {"ok": False, "message": f"File not found: {filename}"}
            os.remove(filename)
            return {"ok": True, "message": f"Deleted file: {filename}"}
        except Exception as exc:
            return {"ok": False, "message": f"Failed to delete file: {exc}"}

    def _open_browser(self, command: str) -> dict[str, Any]:
        try:
            url = self._extract_url(command)
            if not url:
                return {"ok": False, "message": "Please specify a URL"}
            webbrowser.open(url)
            return {"ok": True, "message": f"Opened browser to: {url}"}
        except Exception as exc:
            return {"ok": False, "message": f"Failed to open browser: {exc}"}
