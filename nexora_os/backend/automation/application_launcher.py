"""
Application Launcher Module
Handles launching and controlling system applications
"""
import asyncio
import os
import platform
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(slots=True)
class Application:
    """Represents a system application"""
    name: str
    path: str
    args: list[str] = None
    working_dir: str = None
    enabled: bool = True
    
    def __post_init__(self):
        if self.args is None:
            self.args = []


@dataclass(slots=True)
class RunningProcess:
    """Represents a running application process"""
    pid: int
    app_name: str
    start_time: float
    process: Any


class ApplicationLauncher:
    """Launcher for system applications"""
    
    def __init__(self) -> None:
        self.applications: dict[str, Application] = {}
        self.running_processes: dict[int, RunningProcess] = {}
        self._load_default_applications()
    
    def _load_default_applications(self) -> None:
        """Load default system applications based on OS"""
        system = platform.system()
        
        if system == "Windows":
            default_apps = {
                "notepad": Application("Notepad", "notepad.exe"),
                "calculator": Application("Calculator", "calc.exe"),
                "cmd": Application("Command Prompt", "cmd.exe"),
                "powershell": Application("PowerShell", "powershell.exe"),
                "explorer": Application("File Explorer", "explorer.exe"),
                "mspaint": Application("Paint", "mspaint.exe"),
                "write": Application("WordPad", "write.exe"),
                "control": Application("Control Panel", "control.exe"),
                "taskmgr": Application("Task Manager", "taskmgr.exe"),
            }
        elif system == "Darwin":  # macOS
            default_apps = {
                "textedit": Application("TextEdit", "/Applications/TextEdit.app"),
                "calculator": Application("Calculator", "/Applications/Calculator.app"),
                "terminal": Application("Terminal", "/Applications/Utilities/Terminal.app"),
                "finder": Application("Finder", "/System/Library/CoreServices/Finder.app"),
                "safari": Application("Safari", "/Applications/Safari.app"),
            }
        else:  # Linux
            default_apps = {
                "gedit": Application("Text Editor", "gedit"),
                "gnome-calculator": Application("Calculator", "gnome-calculator"),
                "terminal": Application("Terminal", "gnome-terminal"),
                "nautilus": Application("File Manager", "nautilus"),
                "firefox": Application("Firefox", "firefox"),
            }
        
        self.applications.update(default_apps)
    
    def register_application(self, app_id: str, application: Application) -> bool:
        """
        Register a custom application
        
        Args:
            app_id: Application identifier
            application: Application configuration
            
        Returns:
            True if registered, False otherwise
        """
        if not os.path.exists(application.path) and not application.path.endswith(".exe"):
            return False
        
        self.applications[app_id] = application
        return True
    
    def unregister_application(self, app_id: str) -> bool:
        """Unregister an application"""
        if app_id in self.applications:
            del self.applications[app_id]
            return True
        return False
    
    async def launch(self, app_id: str, args: list[str] = None) -> dict[str, Any]:
        """
        Launch an application
        
        Args:
            app_id: Application identifier
            args: Additional command line arguments
            
        Returns:
            Launch result
        """
        if app_id not in self.applications:
            return {"ok": False, "error": f"Application {app_id} not found"}
        
        app = self.applications[app_id]
        
        if not app.enabled:
            return {"ok": False, "error": f"Application {app_id} is disabled"}
        
        try:
            cmd_args = app.args + (args or [])
            
            process = await asyncio.create_subprocess_exec(
                app.path,
                *cmd_args,
                cwd=app.working_dir or os.getcwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            running_process = RunningProcess(
                pid=process.pid,
                app_name=app.name,
                start_time=time.time(),
                process=process
            )
            
            self.running_processes[process.pid] = running_process
            
            return {
                "ok": True,
                "pid": process.pid,
                "app_name": app.name,
                "message": f"Launched {app.name} (PID: {process.pid})"
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def terminate(self, pid: int) -> dict[str, Any]:
        """
        Terminate a running application
        
        Args:
            pid: Process ID
            
        Returns:
            Termination result
        """
        if pid not in self.running_processes:
            return {"ok": False, "error": f"Process {pid} not found"}
        
        running_process = self.running_processes[pid]
        
        try:
            running_process.process.terminate()
            
            # Wait for process to terminate
            try:
                await asyncio.wait_for(running_process.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Force kill if it doesn't terminate
                running_process.process.kill()
                await running_process.process.wait()
            
            del self.running_processes[pid]
            
            return {
                "ok": True,
                "message": f"Terminated {running_process.app_name} (PID: {pid})"
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def send_input(self, pid: int, input_text: str) -> dict[str, Any]:
        """
        Send input to a running application
        
        Args:
            pid: Process ID
            input_text: Text to send
            
        Returns:
            Result
        """
        if pid not in self.running_processes:
            return {"ok": False, "error": f"Process {pid} not found"}
        
        running_process = self.running_processes[pid]
        
        try:
            if running_process.process.stdin:
                running_process.process.stdin.write(input_text.encode())
                running_process.process.stdin.write(b"\n")
                await running_process.process.stdin.drain()
                return {"ok": True, "message": "Input sent successfully"}
            else:
                return {"ok": False, "error": "Process does not support stdin input"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def list_applications(self) -> list[dict[str, Any]]:
        """List all registered applications"""
        return [
            {
                "id": app_id,
                "name": app.name,
                "path": app.path,
                "enabled": app.enabled
            }
            for app_id, app in self.applications.items()
        ]
    
    def list_running(self) -> list[dict[str, Any]]:
        """List all running processes"""
        return [
            {
                "pid": proc.pid,
                "app_name": proc.app_name,
                "start_time": proc.start_time,
                "runtime": time.time() - proc.start_time
            }
            for proc in self.running_processes.values()
        ]
    
    def get_status(self, pid: int) -> Optional[dict[str, Any]]:
        """Get status of a running process"""
        if pid not in self.running_processes:
            return None
        
        proc = self.running_processes[pid]
        
        # Check if process is still running
        if proc.process.returncode is not None:
            # Process has terminated
            del self.running_processes[pid]
            return None
        
        return {
            "pid": proc.pid,
            "app_name": proc.app_name,
            "start_time": proc.start_time,
            "runtime": time.time() - proc.start_time,
            "status": "running"
        }


# Global application launcher instance
global_app_launcher = ApplicationLauncher()


def register_application(app_id: str, application: Application) -> bool:
    """Register an application using the global launcher"""
    return global_app_launcher.register_application(app_id, application)


async def launch_application(app_id: str, args: list[str] = None) -> dict[str, Any]:
    """Launch an application using the global launcher"""
    return await global_app_launcher.launch(app_id, args)


async def terminate_application(pid: int) -> dict[str, Any]:
    """Terminate an application using the global launcher"""
    return await global_app_launcher.terminate(pid)


def list_applications() -> list[dict[str, Any]]:
    """List applications using the global launcher"""
    return global_app_launcher.list_applications()


def list_running_applications() -> list[dict[str, Any]]:
    """List running applications using the global launcher"""
    return global_app_launcher.list_running()
