from __future__ import annotations

import asyncio
import datetime as dt
import os
import platform
import subprocess
import webbrowser
from pathlib import Path
from typing import Any

from ..core.event_bus import EventBus
from ..vision.engine import VisionEngine


class AutomationEngine:
    def __init__(self, bus: EventBus, vision: VisionEngine) -> None:
        self.bus = bus
        self.vision = vision
        self.history: list[dict[str, Any]] = []

    async def execute(self, command: str) -> dict[str, Any]:
        normalized = command.lower().strip()
        
        # Existing features
        if "screenshot" in normalized or ("screen" in normalized and "ocr" not in normalized):
            result = await self.vision.screen(ocr=False)
        elif "ocr" in normalized:
            result = await self.vision.screen(ocr=True)
        elif "time" in normalized or "நேரம்" in normalized:
            result = {"ok": True, "message": dt.datetime.now().astimezone().strftime("%A, %d %B %Y %I:%M %p")}
        elif "system status" in normalized:
            result = {"ok": True, "message": f"{platform.system()} {platform.release()} on {platform.machine()}"}
        
        # Browser automation
        elif "browser" in normalized or "url" in normalized or "http" in normalized:
            result = await asyncio.to_thread(self._open_browser, command)
            
        # File operations
        elif "create file" in normalized or "write file" in normalized:
            result = await asyncio.to_thread(self._create_file, command)
        elif "read file" in normalized:
            result = await asyncio.to_thread(self._read_file, command)
        elif "delete file" in normalized or "remove file" in normalized:
            result = await asyncio.to_thread(self._delete_file, command)
            
        # App launch
        elif "launch" in normalized or "open" in normalized or "start" in normalized:
            result = await asyncio.to_thread(self._launch_app, command)
        
        else:
            result = {"ok": False, "message": "No registered automation matched that command."}
        
        entry = {"command": command, "result": result, "timestamp": dt.datetime.now().timestamp()}
        self.history.append(entry)
        self.history = self.history[-100:]
        self.bus.publish("automation.executed", entry, "automation_engine")
        self.bus.set_state("automation", {"history": self.history[-20:]}, "automation_engine")
        await asyncio.sleep(0)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "registered_actions": [
                "system status", "time", "screenshot", "ocr screen",
                "launch app", "create file", "read file", "delete file", "open browser"
            ],
            "history": self.history[-20:]
        }

    def _find_windows_app(self, app_name: str) -> str | None:
        """Find an application's AppID or executable path using Windows Start Menu."""
        import json
        import re
        cmd = ['powershell', '-NoProfile', '-Command', 'Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress -Depth 2']
        try:
            output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            apps = json.loads(output)
            if not isinstance(apps, list): apps = [apps]
            pattern = re.compile(re.escape(app_name), re.IGNORECASE)
            best_match = None
            for app in apps:
                if not app or not app.get('Name'): continue
                if app['Name'].lower() == app_name.lower():
                    return app['AppID']
                if pattern.search(app['Name']):
                    best_match = app['AppID']
            return best_match
        except Exception:
            return None

    def _launch_app(self, command: str) -> dict[str, Any]:
        try:
            # Extract app name from command
            words = command.lower().split()
            app_keywords = ["launch", "open", "start"]
            app_name = None
            for i, word in enumerate(words):
                if word in app_keywords and i + 1 < len(words):
                    app_name = " ".join(words[i + 1:])
                    break
            
            if not app_name:
                return {"ok": False, "message": "Please specify an app name (e.g., 'launch notepad')"}
            
            # Common applications mapping
            app_map = {
                "notepad": "notepad.exe",
                "calculator": "calc.exe",
                "cmd": "cmd.exe",
                "powershell": "powershell.exe",
                "explorer": "explorer.exe",
                "chrome": "chrome.exe",
                "edge": "msedge.exe",
                "firefox": "firefox.exe",
                "word": "winword.exe",
                "excel": "excel.exe",
                "notepad++": "notepad++.exe",
            }
            
            # Try to launch the application
            if platform.system() == "Windows":
                app_id = self._find_windows_app(app_name)
                if app_id:
                    if "\\" in app_id or ".exe" in app_id.lower():
                        subprocess.Popen(f'start "" "{app_id}"', shell=True)
                    else:
                        subprocess.Popen(f'explorer.exe shell:AppsFolder\\{app_id}', shell=True)
                    return {"ok": True, "message": f"Launched {app_name}"}
                # Fallback to simple executable start
                exe_name = app_map.get(app_name.lower(), f"{app_name}.exe")
                subprocess.Popen(f'start "" "{exe_name}"', shell=True)
            elif platform.system() == "Darwin":
                exe_name = app_map.get(app_name.lower(), f"{app_name}.app")
                subprocess.Popen(f'open "{exe_name}"', shell=True)
            else:
                exe_name = app_map.get(app_name.lower(), app_name)
                subprocess.Popen(f'"{exe_name}"', shell=True)
                
            return {"ok": True, "message": f"Launched {app_name}"}
        except Exception as e:
            return {"ok": False, "message": f"Failed to launch app: {str(e)}"}

    def _create_file(self, command: str) -> dict[str, Any]:
        try:
            # Extract filename and content from command
            words = command.split()
            if "create file" in command.lower() or "write file" in command.lower():
                file_idx = words.index("file") + 1 if "file" in words else -1
                if file_idx == -1 or file_idx >= len(words):
                    return {"ok": False, "message": "Please specify a filename (e.g., 'create file test.txt')"}
                
                filename = words[file_idx]
                # Remove any punctuation from filename
                filename = filename.rstrip('.,!?')
                
                # Default content
                content = "Created by NEXORA automation"
                
                # Check if there's content after filename
                if file_idx + 1 < len(words):
                    content = " ".join(words[file_idx + 1:])
                
                # Create the file
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                return {"ok": True, "message": f"Created file: {filename}"}
        except Exception as e:
            return {"ok": False, "message": f"Failed to create file: {str(e)}"}

    def _read_file(self, command: str) -> dict[str, Any]:
        try:
            # Extract filename from command
            words = command.split()
            file_idx = words.index("file") + 1 if "file" in words else -1
            if file_idx == -1 or file_idx >= len(words):
                return {"ok": False, "message": "Please specify a filename (e.g., 'read file test.txt')"}
            
            filename = words[file_idx].rstrip('.,!?')
            
            # Check if file exists
            if not os.path.exists(filename):
                return {"ok": False, "message": f"File not found: {filename}"}
            
            # Read the file
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {"ok": True, "message": f"File content:\n{content}"}
        except Exception as e:
            return {"ok": False, "message": f"Failed to read file: {str(e)}"}

    def _delete_file(self, command: str) -> dict[str, Any]:
        try:
            # Extract filename from command
            words = command.split()
            file_idx = words.index("file") + 1 if "file" in words else -1
            if file_idx == -1 or file_idx >= len(words):
                return {"ok": False, "message": "Please specify a filename (e.g., 'delete file test.txt')"}
            
            filename = words[file_idx].rstrip('.,!?')
            
            # Check if file exists
            if not os.path.exists(filename):
                return {"ok": False, "message": f"File not found: {filename}"}
            
            # Delete the file
            os.remove(filename)
            
            return {"ok": True, "message": f"Deleted file: {filename}"}
        except Exception as e:
            return {"ok": False, "message": f"Failed to delete file: {str(e)}"}

    def _open_browser(self, command: str) -> dict[str, Any]:
        try:
            # Extract URL from command
            url = None
            words = command.split()
            
            # Look for http/https URLs
            for word in words:
                if word.startswith("http://") or word.startswith("https://"):
                    url = word
                    break
            
            # If no URL found, try to extract domain
            if not url:
                for word in words:
                    if "." in word and word not in ["browser", "open", "url"]:
                        url = f"https://{word}"
                        break
            
            if not url:
                return {"ok": False, "message": "Please specify a URL (e.g., 'open browser google.com')"}
            
            # Open in default browser
            webbrowser.open(url)
            
            return {"ok": True, "message": f"Opened browser to: {url}"}
        except Exception as e:
            return {"ok": False, "message": f"Failed to open browser: {str(e)}"}
