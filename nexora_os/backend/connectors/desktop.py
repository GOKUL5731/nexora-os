from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STATUS_AVAILABLE = "AVAILABLE"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_DEGRADED = "DEGRADED"
STATUS_FAILED = "FAILED"

try:
    import psutil as _psutil

    _PSUTIL_OK = True
except ImportError:
    _psutil = None
    _PSUTIL_OK = False


@dataclass(slots=True)
class ApplicationRecord:
    application_id: str
    name: str
    executable: str = ""
    path: str = ""
    version: str = ""
    publisher: str = ""
    process_names: list[str] = field(default_factory=list)
    window_titles: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    automation_support: str = "unknown"
    cli_support: bool = False
    api_support: bool = False
    accessibility_support: str = "unknown"
    known_adapters: list[str] = field(default_factory=list)
    status: str = "discovered"
    last_verified: float = 0.0
    launch_method: str = "process"
    app_user_model_id: str = ""


class DesktopConnector:
    """Generic local OS application discovery, launch, observation and control."""

    _WINDOWS_ALIASES = {
        "calc": "calculator",
        "calculator": "calculator",
        "notepad": "notepad",
        "notes": "notepad",
        "text editor": "notepad",
        "file explorer": "explorer",
        "explorer": "explorer",
        "files": "explorer",
        "powershell": "powershell",
        "terminal": "terminal",
        "command prompt": "cmd",
        "cmd": "cmd",
        "paint": "paint",
        "browser": "browser",
        "chrome": "chrome",
        "edge": "edge",
        "firefox": "firefox",
        "vs code": "vscode",
        "vscode": "vscode",
        "visual studio code": "vscode",
        "python ide": "vscode",
    }

    def __init__(self) -> None:
        self._platform = sys_platform()
        self._registry: dict[str, ApplicationRecord] = {}
        self._last_discovery = 0.0
        self._audit: list[dict[str, Any]] = []

    def connect(self) -> dict[str, Any]:
        discovery = self.discover(force=False)
        return {"ok": True, "status": self.health(), "discovered": discovery.get("count", 0)}

    def disconnect(self) -> dict[str, Any]:
        return {"ok": True}

    def health(self) -> str:
        if self._platform != "win32":
            return STATUS_DEGRADED
        if not _PSUTIL_OK:
            return STATUS_DEGRADED
        return STATUS_AVAILABLE

    def get_capabilities(self) -> list[str]:
        return [
            "discover_apps",
            "resolve_app",
            "launch_app",
            "wait_for_process",
            "wait_for_window",
            "list_apps",
            "list_windows",
            "list_monitors",
            "inspect",
            "focus_window",
            "close_app",
            "system_info",
            "lock_screen",
            "audit_log",
        ]

    def execute(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        action = (action or "").strip()
        params = params or {}
        started = time.time()
        try:
            if action in {"discover", "discover_apps"}:
                result = self.discover(force=bool(params.get("force", False)))
            elif action in {"resolve", "resolve_app"}:
                result = self.resolve(str(params.get("app_name") or params.get("query") or ""))
            elif action == "launch_app":
                result = self.launch(
                    str(params.get("app_name") or params.get("query") or ""),
                    args=params.get("args") if isinstance(params.get("args"), list) else None,
                    wait_seconds=float(params.get("wait_seconds", 8.0)),
                )
            elif action == "wait_for_process":
                result = self.wait_for_process(
                    str(params.get("process_name") or ""),
                    timeout=float(params.get("timeout", 8.0)),
                )
            elif action == "wait_for_window":
                result = self.wait_for_window(
                    title_contains=str(params.get("title_contains") or ""),
                    process_name=str(params.get("process_name") or ""),
                    timeout=float(params.get("timeout", 8.0)),
                )
            elif action in {"list_apps", "applications"}:
                result = self.list_apps()
            elif action in {"list_windows", "windows"}:
                result = self.list_windows()
            elif action in {"list_monitors", "monitors"}:
                result = self.list_monitors()
            elif action == "inspect":
                result = self.inspect(str(params.get("app_name") or params.get("query") or ""))
            elif action == "focus_window":
                result = self.focus_window(
                    title_contains=str(params.get("title_contains") or ""),
                    process_name=str(params.get("process_name") or ""),
                )
            elif action == "close_app":
                result = self.close_app(
                    pid=int(params["pid"]) if params.get("pid") else None,
                    app_name=str(params.get("app_name") or ""),
                )
            elif action == "system_info":
                result = self.system_info()
            elif action == "lock_screen":
                result = self.lock_screen()
            elif action == "audit_log":
                result = {"ok": True, "entries": self._audit[-100:]}
            else:
                result = {"ok": False, "error": f"Unknown action: {action}"}
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}

        self._record_audit(action, params, result, time.time() - started)
        return result

    def discover(self, force: bool = False) -> dict[str, Any]:
        if self._registry and not force and time.time() - self._last_discovery < 60:
            return {"ok": True, "count": len(self._registry), "applications": self._records()}

        records: dict[str, ApplicationRecord] = {}
        if self._platform == "win32":
            records.update(self._discover_windows_known_apps())
            for key, record in self._discover_windows_start_apps().items():
                # Prefer known executable records over weaker Start-menu records.
                # They give us better process observation and close semantics.
                records.setdefault(key, record)
        else:
            records.update(self._discover_path_apps(["xdg-open", "firefox", "code", "gnome-terminal"]))

        self._registry = records
        self._last_discovery = time.time()
        return {"ok": True, "count": len(records), "applications": self._records()}

    def resolve(self, query: str) -> dict[str, Any]:
        query = normalize_query(query)
        if not query:
            return {"ok": False, "error": "resolve_app requires app_name or query"}
        self.discover(force=False)

        alias = self._WINDOWS_ALIASES.get(query, query)
        if alias == "browser":
            for browser in ("edge", "chrome", "firefox"):
                if browser in self._registry:
                    alias = browser
                    break

        candidates = []
        for record in self._registry.values():
            haystack = " ".join(
                [
                    record.application_id,
                    record.name,
                    record.executable,
                    record.path,
                    " ".join(record.process_names),
                ]
            ).lower()
            score = 0
            if record.application_id == alias:
                score += 100
            if record.name.lower() == query:
                score += 90
            if alias in haystack:
                score += 50
            if query in haystack:
                score += 30
            if score:
                candidates.append((score, record))

        if not candidates:
            return {"ok": False, "error": f"Application not found: {query}", "query": query}

        candidates.sort(key=lambda row: row[0], reverse=True)
        selected = candidates[0][1]
        return {
            "ok": True,
            "query": query,
            "application": asdict(selected),
            "alternatives": [asdict(row[1]) for row in candidates[1:5]],
        }

    def launch(self, query: str, args: list[str] | None = None, wait_seconds: float = 8.0) -> dict[str, Any]:
        resolved = self.resolve(query)
        if not resolved.get("ok"):
            return resolved
        record = ApplicationRecord(**resolved["application"])
        args = args or []

        if record.launch_method == "uwp" and record.app_user_model_id:
            command = ["explorer.exe", f"shell:AppsFolder\\{record.app_user_model_id}"]
            process = subprocess.Popen(command)
        else:
            executable = record.path or record.executable
            if not executable:
                return {"ok": False, "error": f"No executable for {record.name}", "application": asdict(record)}
            command = [executable, *args]
            process = subprocess.Popen(command, cwd=os.getcwd())

        process_names = record.process_names or [Path(record.executable).name or Path(record.path).name]
        observed_process = self._wait_for_any_process(process.pid, process_names, wait_seconds)
        observed_window = self._wait_for_any_window(record, wait_seconds)

        verified = bool(observed_process.get("found")) or bool(observed_window.get("found"))
        result = {
            "ok": verified,
            "application": asdict(record),
            "pid": process.pid,
            "command": command,
            "risk": "LOW",
            "permission_checked": True,
            "observation": {
                "process": observed_process,
                "window": observed_window,
            },
            "verification": {
                "process_detected": bool(observed_process.get("found")),
                "window_detected": bool(observed_window.get("found")),
                "verified": verified,
            },
        }
        if verified:
            result["message"] = f"{record.name} launched and was observed."
        else:
            result["error"] = f"{record.name} launch was started but could not be verified."
        return result

    def wait_for_process(self, process_name: str, timeout: float = 8.0) -> dict[str, Any]:
        if not process_name:
            return {"ok": False, "error": "wait_for_process requires process_name"}
        result = self._wait_for_any_process(None, [process_name], timeout)
        return {"ok": bool(result.get("found")), **result}

    def wait_for_window(self, title_contains: str = "", process_name: str = "", timeout: float = 8.0) -> dict[str, Any]:
        deadline = time.time() + timeout
        while time.time() <= deadline:
            windows = self._windows()
            for window in windows:
                title_ok = not title_contains or title_contains.lower() in window.get("title", "").lower()
                proc_ok = not process_name or process_name.lower() in window.get("process_name", "").lower()
                if title_ok and proc_ok:
                    return {"ok": True, "found": True, "window": window, "windows_checked": len(windows)}
            time.sleep(0.2)
        return {"ok": False, "found": False, "windows_checked": len(self._windows())}

    def list_apps(self) -> dict[str, Any]:
        self.discover(force=False)
        return {"ok": True, "applications": self._records(), "count": len(self._registry)}

    def list_windows(self) -> dict[str, Any]:
        windows = self._windows()
        return {"ok": True, "windows": windows, "count": len(windows)}

    def list_monitors(self) -> dict[str, Any]:
        """Return the real Windows monitor topology, including negative bounds."""
        if self._platform != "win32":
            return {"ok": False, "status": STATUS_DEGRADED, "monitors": [], "error": "windows_only"}
        script = """
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Screen]::AllScreens | ForEach-Object {
  [pscustomobject]@{
    id = $_.DeviceName; primary = [bool]$_.Primary
    x = $_.Bounds.X; y = $_.Bounds.Y; width = $_.Bounds.Width; height = $_.Bounds.Height
    work_x = $_.WorkingArea.X; work_y = $_.WorkingArea.Y
    work_width = $_.WorkingArea.Width; work_height = $_.WorkingArea.Height
  }
} | ConvertTo-Json -Compress -Depth 3
"""
        try:
            completed = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=10)
            if completed.returncode != 0 or not completed.stdout.strip():
                return {"ok": False, "status": STATUS_FAILED, "monitors": [], "error": completed.stderr.strip() or "monitor_query_failed"}
            payload = json.loads(completed.stdout)
            monitors = payload if isinstance(payload, list) else [payload]
            return {"ok": True, "status": STATUS_AVAILABLE, "monitors": monitors, "count": len(monitors)}
        except Exception as exc:
            return {"ok": False, "status": STATUS_FAILED, "monitors": [], "error": str(exc)}

    def inspect(self, query: str) -> dict[str, Any]:
        resolved = self.resolve(query)
        if not resolved.get("ok"):
            return resolved
        record = ApplicationRecord(**resolved["application"])
        processes = self._matching_processes(record.process_names)
        windows = [
            window
            for window in self._windows()
            if window.get("process_name", "").lower() in {p.lower() for p in record.process_names}
            or any(token.lower() in window.get("title", "").lower() for token in [record.name, record.application_id])
        ]
        return {
            "ok": True,
            "application": asdict(record),
            "processes": processes,
            "windows": windows,
            "verification": {
                "installed": True,
                "running": bool(processes),
                "window_visible": bool(windows),
            },
        }

    def focus_window(self, title_contains: str = "", process_name: str = "") -> dict[str, Any]:
        window = self.wait_for_window(title_contains=title_contains, process_name=process_name, timeout=0.2)
        if not window.get("ok"):
            return {"ok": False, "error": "No matching window found", "observation": window}
        if self._platform != "win32":
            return {"ok": False, "error": "focus_window is currently implemented only for Windows"}
        hwnd = int(window["window"]["handle"])
        script = (
            "$sig='[DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);';"
            "Add-Type -MemberDefinition $sig -Name Win32Focus -Namespace Native;"
            f"[Native.Win32Focus]::SetForegroundWindow([IntPtr]{hwnd}) | Out-Null"
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return {
            "ok": completed.returncode == 0,
            "window": window["window"],
            "verification": {"focused_request_returncode": completed.returncode},
            "error": completed.stderr.strip() if completed.returncode else "",
        }

    def close_app(self, pid: int | None = None, app_name: str = "") -> dict[str, Any]:
        targets: list[dict[str, Any]] = []
        if pid:
            targets = [p for p in self._processes() if int(p.get("pid", -1)) == pid]
        elif app_name:
            resolved = self.resolve(app_name)
            if not resolved.get("ok"):
                return resolved
            record = ApplicationRecord(**resolved["application"])
            targets = self._matching_processes(record.process_names)
        else:
            return {"ok": False, "error": "close_app requires pid or app_name"}

        closed = []
        errors = []
        for target in targets:
            try:
                if not _PSUTIL_OK:
                    subprocess.run(["taskkill", "/PID", str(target["pid"]), "/T"], capture_output=True, timeout=8)
                else:
                    proc = _psutil.Process(int(target["pid"]))
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except _psutil.TimeoutExpired:
                        proc.kill()
                closed.append(target)
            except Exception as exc:
                errors.append({"target": target, "error": str(exc)})
        return {"ok": bool(closed) and not errors, "closed": closed, "errors": errors}

    def system_info(self) -> dict[str, Any]:
        if not _PSUTIL_OK:
            return {"ok": False, "error": "psutil not installed. Install with: pip install psutil"}
        vm = _psutil.virtual_memory()
        disk = _psutil.disk_usage("/")
        return {
            "ok": True,
            "cpu_percent": _psutil.cpu_percent(interval=0.2),
            "ram_gb_used": round(vm.used / 1e9, 2),
            "ram_gb_total": round(vm.total / 1e9, 2),
            "ram_percent": vm.percent,
            "disk_percent": disk.percent,
            "platform": self._platform,
        }

    def lock_screen(self) -> dict[str, Any]:
        if self._platform == "win32":
            subprocess.run(["rundll32", "user32.dll,LockWorkStation"], check=True)
        elif self._platform == "darwin":
            subprocess.run(
                ["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"],
                check=True,
            )
        else:
            subprocess.run(["xdg-screensaver", "lock"], check=True)
        return {"ok": True, "message": "Screen locked", "risk": "HIGH", "permission_checked": True}

    def _discover_windows_known_apps(self) -> dict[str, ApplicationRecord]:
        candidates = {
            "notepad": ("Notepad", "notepad.exe"),
            "calculator": ("Calculator", "calc.exe"),
            "cmd": ("Command Prompt", "cmd.exe"),
            "powershell": ("PowerShell", "powershell.exe"),
            "explorer": ("File Explorer", "explorer.exe"),
            "paint": ("Paint", "mspaint.exe"),
            "edge": ("Microsoft Edge", "msedge.exe"),
            "chrome": ("Google Chrome", "chrome.exe"),
            "firefox": ("Firefox", "firefox.exe"),
            "vscode": ("Visual Studio Code", "code.cmd"),
            "terminal": ("Windows Terminal", "wt.exe"),
        }
        records: dict[str, ApplicationRecord] = {}
        for app_id, (name, exe) in candidates.items():
            resolved = shutil.which(exe)
            if resolved or exe in {"notepad.exe", "calc.exe", "cmd.exe", "powershell.exe", "explorer.exe", "mspaint.exe"}:
                records[app_id] = ApplicationRecord(
                    application_id=app_id,
                    name=name,
                    executable=exe,
                    path=resolved or exe,
                    process_names=self._process_names_for(app_id, exe),
                    capabilities=["launch", "process_observe", "window_observe", "keyboard_fallback"],
                    automation_support="windows",
                    cli_support=app_id in {"cmd", "powershell", "vscode", "terminal"},
                    accessibility_support="possible",
                    known_adapters=[app_id] if app_id in {"vscode", "terminal"} else [],
                    status="available",
                )
        return records

    def _discover_windows_start_apps(self) -> dict[str, ApplicationRecord]:
        script = "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress -Depth 2"
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if completed.returncode != 0 or not completed.stdout.strip():
                return {}
            payload = json.loads(completed.stdout)
            apps = payload if isinstance(payload, list) else [payload]
        except Exception:
            return {}

        records: dict[str, ApplicationRecord] = {}
        for app in apps:
            name = str(app.get("Name") or "").strip()
            appid = str(app.get("AppID") or "").strip()
            if not name or not appid:
                continue
            app_key = slug(name)
            if app_key in self._registry or app_key in records:
                continue
            records[app_key] = ApplicationRecord(
                application_id=app_key,
                name=name,
                app_user_model_id=appid,
                process_names=[],
                window_titles=[name],
                capabilities=["launch", "window_observe", "keyboard_fallback"],
                automation_support="windows_start_app",
                accessibility_support="possible",
                status="available",
                launch_method="uwp",
            )
        return records

    def _discover_path_apps(self, executables: list[str]) -> dict[str, ApplicationRecord]:
        records = {}
        for exe in executables:
            path = shutil.which(exe)
            if not path:
                continue
            app_id = slug(Path(exe).stem)
            records[app_id] = ApplicationRecord(
                application_id=app_id,
                name=Path(exe).stem,
                executable=exe,
                path=path,
                process_names=[Path(exe).name],
                capabilities=["launch", "process_observe"],
                status="available",
            )
        return records

    def _records(self) -> list[dict[str, Any]]:
        return sorted((asdict(record) for record in self._registry.values()), key=lambda row: row["name"].lower())

    def _processes(self) -> list[dict[str, Any]]:
        if not _PSUTIL_OK:
            return []
        rows = []
        for proc in _psutil.process_iter(["pid", "name", "exe", "status", "create_time"]):
            try:
                info = proc.info
                rows.append(
                    {
                        "pid": info.get("pid"),
                        "name": info.get("name") or "",
                        "exe": info.get("exe") or "",
                        "status": info.get("status") or "",
                        "create_time": info.get("create_time") or 0,
                    }
                )
            except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                continue
        return rows

    def _matching_processes(self, names: list[str]) -> list[dict[str, Any]]:
        wanted = {Path(name).name.lower() for name in names if name}
        if not wanted:
            return []
        return [proc for proc in self._processes() if proc.get("name", "").lower() in wanted]

    def _wait_for_any_process(self, pid: int | None, names: list[str], timeout: float) -> dict[str, Any]:
        deadline = time.time() + timeout
        while time.time() <= deadline:
            processes = self._processes()
            for proc in processes:
                if pid and int(proc.get("pid") or -1) == pid:
                    return {"found": True, "process": proc, "matched_by": "pid"}
                if proc.get("name", "").lower() in {Path(name).name.lower() for name in names if name}:
                    return {"found": True, "process": proc, "matched_by": "name"}
            time.sleep(0.2)
        return {"found": False, "processes_checked": len(self._processes())}

    def _wait_for_any_window(self, record: ApplicationRecord, timeout: float) -> dict[str, Any]:
        deadline = time.time() + timeout
        process_names = {name.lower() for name in record.process_names}
        title_tokens = {record.name.lower(), record.application_id.lower(), *(t.lower() for t in record.window_titles)}
        while time.time() <= deadline:
            windows = self._windows()
            for window in windows:
                title = window.get("title", "").lower()
                proc = window.get("process_name", "").lower()
                if proc in process_names or any(token and token in title for token in title_tokens):
                    return {"found": True, "window": window}
            time.sleep(0.2)
        return {"found": False, "windows_checked": len(self._windows())}

    def _windows(self) -> list[dict[str, Any]]:
        if self._platform != "win32":
            return []
        script = r"""
$sig = @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Win32Enum {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr hWnd, out int processId);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
'@
Add-Type $sig -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.Windows.Forms
$items = New-Object System.Collections.Generic.List[object]
[Win32Enum]::EnumWindows({
  param($hWnd, $lParam)
  if ([Win32Enum]::IsWindowVisible($hWnd)) {
    $builder = New-Object System.Text.StringBuilder 512
    [void][Win32Enum]::GetWindowText($hWnd, $builder, $builder.Capacity)
    $title = $builder.ToString()
    if ($title.Trim().Length -gt 0) {
      $procId = 0
      [void][Win32Enum]::GetWindowThreadProcessId($hWnd, [ref]$procId)
      $procName = ""
      $exe = ""
      try { $proc = Get-Process -Id $procId -ErrorAction Stop; $procName = $proc.ProcessName + ".exe"; $exe = $proc.Path } catch {}
      $rect = New-Object Win32Enum+RECT
      [void][Win32Enum]::GetWindowRect($hWnd, [ref]$rect)
      $screen = [System.Windows.Forms.Screen]::FromHandle($hWnd)
      $items.Add([pscustomobject]@{
        handle = $hWnd.ToInt64(); pid = $procId; process_name = $procName; executable = $exe; title = $title;
        x = $rect.Left; y = $rect.Top; width = ($rect.Right - $rect.Left); height = ($rect.Bottom - $rect.Top);
        visible = $true; minimized = [Win32Enum]::IsIconic($hWnd); maximized = [Win32Enum]::IsZoomed($hWnd);
        focused = ($hWnd -eq [Win32Enum]::GetForegroundWindow()); monitor_id = $screen.DeviceName
      }) | Out-Null
    }
  }
  return $true
}, [IntPtr]::Zero) | Out-Null
$items | ConvertTo-Json -Compress -Depth 3
"""
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if completed.returncode != 0 or not completed.stdout.strip():
                return []
            payload = json.loads(completed.stdout)
            return payload if isinstance(payload, list) else [payload]
        except Exception:
            return []

    def _process_names_for(self, app_id: str, executable: str) -> list[str]:
        mapping = {
            "calculator": ["CalculatorApp.exe", "ApplicationFrameHost.exe", "calc.exe"],
            "explorer": ["explorer.exe"],
            "powershell": ["powershell.exe", "pwsh.exe"],
            "terminal": ["WindowsTerminal.exe", "wt.exe"],
            "vscode": ["Code.exe", "code.exe"],
            "edge": ["msedge.exe"],
            "chrome": ["chrome.exe"],
            "firefox": ["firefox.exe"],
        }
        return mapping.get(app_id, [Path(executable).name])

    def _record_audit(self, action: str, params: dict[str, Any], result: dict[str, Any], duration: float) -> None:
        entry = {
            "timestamp": time.time(),
            "action": action,
            "params": {k: v for k, v in params.items() if k.lower() not in {"password", "token", "secret"}},
            "ok": bool(result.get("ok")),
            "duration_ms": int(duration * 1000),
            "risk": result.get("risk", "LOW"),
            "permission_checked": bool(result.get("permission_checked", action not in {"launch_app", "lock_screen"})),
        }
        self._audit.append(entry)
        self._audit = self._audit[-500:]


def sys_platform() -> str:
    if platform.system() == "Windows":
        return "win32"
    if platform.system() == "Darwin":
        return "darwin"
    return "linux"


def normalize_query(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def slug(value: str) -> str:
    text = normalize_query(value)
    cleaned = []
    last_dash = False
    for char in text:
        if char.isalnum():
            cleaned.append(char)
            last_dash = False
        elif not last_dash:
            cleaned.append("-")
            last_dash = True
    return "".join(cleaned).strip("-")
