"""
System Control Module
Provides comprehensive system control capabilities
"""
import asyncio
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional


class SystemControl:
    """System control operations"""
    
    def __init__(self) -> None:
        self.system = platform.system()
        self._pending_operations: dict[str, Any] = {}
    
    async def shutdown(self, delay: int = 0) -> dict[str, Any]:
        """
        Shutdown the system
        
        Args:
            delay: Delay in seconds before shutdown
            
        Returns:
            Operation result
        """
        try:
            if self.system == "Windows":
                if delay > 0:
                    subprocess.run(["shutdown", "/s", "/t", str(delay)], check=True)
                else:
                    subprocess.run(["shutdown", "/s", "/t", "0"], check=True)
            elif self.system == "Darwin":  # macOS
                subprocess.run(["shutdown", "-h", "now"], check=True)
            else:  # Linux
                subprocess.run(["shutdown", "-h", "now"], check=True)
            
            return {"ok": True, "message": f"System shutdown scheduled in {delay} seconds"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def restart(self, delay: int = 0) -> dict[str, Any]:
        """
        Restart the system
        
        Args:
            delay: Delay in seconds before restart
            
        Returns:
            Operation result
        """
        try:
            if self.system == "Windows":
                if delay > 0:
                    subprocess.run(["shutdown", "/r", "/t", str(delay)], check=True)
                else:
                    subprocess.run(["shutdown", "/r", "/t", "0"], check=True)
            elif self.system == "Darwin":  # macOS
                subprocess.run(["shutdown", "-r", "now"], check=True)
            else:  # Linux
                subprocess.run(["shutdown", "-r", "now"], check=True)
            
            return {"ok": True, "message": f"System restart scheduled in {delay} seconds"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def cancel_shutdown(self) -> dict[str, Any]:
        """Cancel pending shutdown/restart"""
        try:
            if self.system == "Windows":
                subprocess.run(["shutdown", "/a"], check=True)
            elif self.system == "Darwin":  # macOS
                subprocess.run(["killall", "shutdown"], check=False)
            else:  # Linux
                subprocess.run(["shutdown", "-c"], check=True)
            
            return {"ok": True, "message": "Shutdown cancelled"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def sleep(self) -> dict[str, Any]:
        """Put system to sleep"""
        try:
            if self.system == "Windows":
                subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=True)
            elif self.system == "Darwin":  # macOS
                subprocess.run(["pmset", "sleepnow"], check=True)
            else:  # Linux
                subprocess.run(["systemctl", "suspend"], check=True)
            
            return {"ok": True, "message": "System going to sleep"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def lock_screen(self) -> dict[str, Any]:
        """Lock the screen"""
        try:
            if self.system == "Windows":
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
            elif self.system == "Darwin":  # macOS
                subprocess.run(["/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession", "-suspend"], check=True)
            else:  # Linux
                subprocess.run(["xdg-screensaver", "lock"], check=True)
            
            return {"ok": True, "message": "Screen locked"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def set_volume(self, volume: int) -> dict[str, Any]:
        """
        Set system volume
        
        Args:
            volume: Volume level (0-100)
            
        Returns:
            Operation result
        """
        try:
            volume = max(0, min(100, volume))
            
            if self.system == "Windows":
                # Requires pycaw or similar library
                return {"ok": False, "error": "Volume control requires additional library on Windows"}
            elif self.system == "Darwin":  # macOS
                subprocess.run(["osascript", "-e", f"set volume output volume {volume}"], check=True)
            else:  # Linux
                subprocess.run(["amixer", "set", "Master", f"{volume}%"], check=True)
            
            return {"ok": True, "message": f"Volume set to {volume}%"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def get_system_info(self) -> dict[str, Any]:
        """Get comprehensive system information"""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "ok": True,
                "system": {
                    "platform": platform.platform(),
                    "system": self.system,
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                },
                "cpu": {
                    "percent": cpu_percent,
                    "count": psutil.cpu_count(),
                    "count_logical": psutil.cpu_count(logical=True)
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent
                }
            }
        except ImportError:
            # Fallback without psutil
            return {
                "ok": True,
                "system": {
                    "platform": platform.platform(),
                    "system": self.system,
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                }
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def list_processes(self) -> dict[str, Any]:
        """List running processes"""
        try:
            import psutil
            
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append({
                        "pid": proc.info['pid'],
                        "name": proc.info['name'],
                        "username": proc.info['username'],
                        "cpu_percent": proc.info['cpu_percent'],
                        "memory_percent": proc.info['memory_percent']
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return {"ok": True, "processes": processes}
        except ImportError:
            return {"ok": False, "error": "Process listing requires psutil library"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def kill_process(self, pid: int) -> dict[str, Any]:
        """
        Kill a process by PID
        
        Args:
            pid: Process ID
            
        Returns:
            Operation result
        """
        try:
            import psutil
            proc = psutil.Process(pid)
            proc.kill()
            return {"ok": True, "message": f"Process {pid} killed"}
        except ImportError:
            return {"ok": False, "error": "Process control requires psutil library"}
        except psutil.NoSuchProcess:
            return {"ok": False, "error": f"Process {pid} not found"}
        except psutil.AccessDenied:
            return {"ok": False, "error": f"Access denied to process {pid}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def create_directory(self, path: str) -> dict[str, Any]:
        """Create a directory"""
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return {"ok": True, "message": f"Directory created: {path}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def delete_file(self, path: str) -> dict[str, Any]:
        """Delete a file or directory"""
        try:
            path_obj = Path(path)
            if path_obj.is_file():
                path_obj.unlink()
            elif path_obj.is_dir():
                shutil.rmtree(path_obj)
            return {"ok": True, "message": f"Deleted: {path}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def copy_file(self, source: str, destination: str) -> dict[str, Any]:
        """Copy a file or directory"""
        try:
            source_obj = Path(source)
            dest_obj = Path(destination)
            
            if source_obj.is_file():
                shutil.copy2(source, destination)
            elif source_obj.is_dir():
                shutil.copytree(source, destination)
            
            return {"ok": True, "message": f"Copied {source} to {destination}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def move_file(self, source: str, destination: str) -> dict[str, Any]:
        """Move a file or directory"""
        try:
            shutil.move(source, destination)
            return {"ok": True, "message": f"Moved {source} to {destination}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def list_directory(self, path: str) -> dict[str, Any]:
        """List contents of a directory"""
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                return {"ok": False, "error": f"Path does not exist: {path}"}
            
            if not path_obj.is_dir():
                return {"ok": False, "error": f"Path is not a directory: {path}"}
            
            contents = []
            for item in path_obj.iterdir():
                contents.append({
                    "name": item.name,
                    "path": str(item),
                    "is_file": item.is_file(),
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else 0
                })
            
            return {"ok": True, "path": path, "contents": contents}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def open_file(self, path: str) -> dict[str, Any]:
        """Open a file with default application"""
        try:
            if self.system == "Windows":
                os.startfile(path)
            elif self.system == "Darwin":  # macOS
                subprocess.run(["open", path], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", path], check=True)
            
            return {"ok": True, "message": f"Opened: {path}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def empty_trash(self) -> dict[str, Any]:
        """Empty the recycle bin/trash"""
        try:
            if self.system == "Windows":
                subprocess.run(["powershell", "-Command", "Clear-RecycleBin", "-Force"], check=True)
            elif self.system == "Darwin":  # macOS
                subprocess.run(["rm", "-rf", "~/.Trash/*"], check=True)
            else:  # Linux
                subprocess.run(["rm", "-rf", "~/.local/share/Trash/*"], check=True)
            
            return {"ok": True, "message": "Trash emptied"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# Global system control instance
global_system_control = SystemControl()


async def shutdown_system(delay: int = 0) -> dict[str, Any]:
    """Shutdown system using global controller"""
    return await global_system_control.shutdown(delay)


async def restart_system(delay: int = 0) -> dict[str, Any]:
    """Restart system using global controller"""
    return await global_system_control.restart(delay)


async def get_system_info() -> dict[str, Any]:
    """Get system info using global controller"""
    return await global_system_control.get_system_info()


async def list_processes() -> dict[str, Any]:
    """List processes using global controller"""
    return await global_system_control.list_processes()
