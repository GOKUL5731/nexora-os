"""
JARVIS System Agent — Windows-native file, clipboard, process, and system control.
Uses only stdlib + psutil (optional). No Linux-specific commands.
"""

import asyncio
import logging
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from agents.agent_registry import BaseAgent

logger = logging.getLogger("jarvis.agents.system")
IS_WIN = sys.platform == "win32"


class SystemAgent(BaseAgent):
    def supported_tools(self):
        return [
            "read_file", "write_file", "delete_file", "list_directory",
            "create_directory", "copy_file", "move_file", "search_files",
            "take_screenshot", "clipboard_read", "clipboard_write",
            "get_system_info", "run_command", "system_command",
            "open_app", "open_application",
        ]

    async def execute(self, tool: str, args: dict) -> Any:
        handlers = {
            "read_file":        self.read_file,
            "write_file":       self.write_file,
            "delete_file":      self.delete_file,
            "list_directory":   self.list_dir,
            "create_directory": self.create_dir,
            "copy_file":        self.copy_file,
            "move_file":        self.move_file,
            "search_files":     self.search_files,
            "take_screenshot":  self.screenshot,
            "clipboard_read":   self.clipboard_read,
            "clipboard_write":  self.clipboard_write,
            "get_system_info":  self.sys_info,
            "run_command":      self.run_cmd,
            "system_command":   self.run_cmd,
            "open_app":         self.open_app,
            "open_application": self.open_app,
        }
        fn = handlers.get(tool)
        if not fn:
            raise ValueError(f"SystemAgent: unknown tool '{tool}'")
        return await fn(args)

    # ── Files ───────────────────────────────────────────────────────────────
    async def read_file(self, args: dict) -> dict:
        p = Path(args["path"]).expanduser().resolve()
        if not p.exists():
            return {"error": f"Not found: {p}"}
        try:
            raw = p.read_bytes()
            try:
                return {"path": str(p), "content": raw.decode("utf-8"), "size": len(raw)}
            except UnicodeDecodeError:
                return {"path": str(p), "content": "[binary file]", "size": len(raw)}
        except PermissionError:
            return {"error": f"Permission denied: {p}"}

    async def write_file(self, args: dict) -> dict:
        p = Path(args["path"]).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        content = args.get("content", "")
        mode = args.get("mode", "w")
        with open(p, mode, encoding="utf-8") as f:
            f.write(content)
        return {"written": str(p), "bytes": len(content.encode())}

    async def delete_file(self, args: dict) -> dict:
        p = Path(args["path"]).expanduser().resolve()
        if not p.exists():
            return {"error": f"Not found: {p}"}
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return {"deleted": str(p)}

    async def list_dir(self, args: dict) -> dict:
        p = Path(args.get("path", ".")).expanduser().resolve()
        if not p.exists():
            return {"error": f"Not found: {p}"}
        items = [
            {"name": i.name, "type": "dir" if i.is_dir() else "file",
             "size": i.stat().st_size if i.is_file() else None}
            for i in sorted(p.iterdir())
        ]
        return {"path": str(p), "items": items, "count": len(items)}

    async def create_dir(self, args: dict) -> dict:
        p = Path(args["path"]).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return {"created": str(p)}

    async def copy_file(self, args: dict) -> dict:
        src = Path(args["source"]).expanduser()
        dst = Path(args["destination"]).expanduser()
        shutil.copy2(src, dst)
        return {"copied": str(src), "to": str(dst)}

    async def move_file(self, args: dict) -> dict:
        src = Path(args["source"]).expanduser()
        dst = Path(args["destination"]).expanduser()
        shutil.move(str(src), str(dst))
        return {"moved": str(src), "to": str(dst)}

    async def search_files(self, args: dict) -> dict:
        base    = Path(args.get("directory", ".")).expanduser()
        pattern = args.get("pattern", "*")
        matches = [str(p) for p in base.rglob(pattern)][:100]
        return {"matches": matches, "count": len(matches)}

    # ── Screen & Clipboard ──────────────────────────────────────────────────
    async def screenshot(self, args: dict) -> dict:
        from pathlib import Path
        import datetime

        save_dir = Path(args.get("save_path", "screenshots"))
        save_dir.mkdir(parents=True, exist_ok=True)
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = save_dir / f"screen_{ts}.png"

        loop = asyncio.get_event_loop()
        def _snap():
            try:
                import pyautogui
                img = pyautogui.screenshot()
                img.save(str(dest))
                return {"saved": str(dest), "size": f"{img.width}x{img.height}"}
            except ImportError:
                # Fallback: Windows-only PIL screenshot
                try:
                    from PIL import ImageGrab
                    img = ImageGrab.grab()
                    img.save(str(dest))
                    return {"saved": str(dest)}
                except ImportError:
                    return {"error": "Install pyautogui: pip install pyautogui pillow"}
        return await loop.run_in_executor(None, _snap)

    async def clipboard_read(self, args: dict) -> dict:
        loop = asyncio.get_event_loop()
        def _read():
            if IS_WIN:
                import subprocess
                r = subprocess.run(
                    ["powershell", "-command", "Get-Clipboard"],
                    capture_output=True, text=True
                )
                return {"content": r.stdout.strip()}
            else:
                try:
                    import pyperclip
                    return {"content": pyperclip.paste()}
                except ImportError:
                    return {"error": "Install pyperclip: pip install pyperclip"}
        return await loop.run_in_executor(None, _read)

    async def clipboard_write(self, args: dict) -> dict:
        content = args.get("content", "")
        loop = asyncio.get_event_loop()
        def _write():
            if IS_WIN:
                subprocess.run(
                    ["powershell", "-command", f"Set-Clipboard -Value '{content}'"],
                    capture_output=True
                )
                return {"ok": True}
            else:
                try:
                    import pyperclip
                    pyperclip.copy(content)
                    return {"ok": True}
                except ImportError:
                    return {"error": "Install pyperclip"}
        return await loop.run_in_executor(None, _write)

    # ── System Info ─────────────────────────────────────────────────────────
    async def sys_info(self, args: dict) -> dict:
        loop = asyncio.get_event_loop()
        def _info():
            info = {
                "os": platform.system(),
                "os_version": platform.version()[:50],
                "python": platform.python_version(),
                "cpu_cores": os.cpu_count(),
            }
            try:
                import psutil
                info["cpu_percent"] = psutil.cpu_percent(interval=0.5)
                ram = psutil.virtual_memory()
                info["ram_total_gb"]      = round(ram.total / 1e9, 1)
                info["ram_used_percent"]  = ram.percent
                disk = psutil.disk_usage("C:\\" if IS_WIN else "/")
                info["disk_total_gb"]    = round(disk.total / 1e9, 1)
                info["disk_free_gb"]     = round(disk.free / 1e9, 1)
            except ImportError:
                info["note"] = "Install psutil for full stats: pip install psutil"
            return info
        return await loop.run_in_executor(None, _info)

    # ── Commands & Apps ─────────────────────────────────────────────────────
    async def run_cmd(self, args: dict) -> dict:
        cmd     = args.get("command", "")
        timeout = args.get("timeout", 30)
        if not cmd:
            return {"error": "No command provided"}

        loop = asyncio.get_event_loop()
        def _run():
            try:
                r = subprocess.run(
                    cmd, shell=True, capture_output=True,
                    text=True, timeout=timeout,
                    # Windows: avoid opening console windows
                    creationflags=subprocess.CREATE_NO_WINDOW if IS_WIN else 0,
                )
                return {
                    "command": cmd,
                    "returncode": r.returncode,
                    "stdout": r.stdout[:2000],
                    "stderr": r.stderr[:500],
                    "ok": r.returncode == 0,
                }
            except subprocess.TimeoutExpired:
                return {"error": f"Timed out after {timeout}s"}
            except Exception as e:
                return {"error": str(e)}
        return await loop.run_in_executor(None, _run)

    async def open_app(self, args: dict) -> dict:
        name = args.get("name", "")
        loop = asyncio.get_event_loop()
        def _open():
            try:
                if IS_WIN:
                    os.startfile(name)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-a", name])
                else:
                    subprocess.Popen(["xdg-open", name])
                return {"opened": name}
            except Exception as e:
                return {"error": str(e)}
        return await loop.run_in_executor(None, _open)
