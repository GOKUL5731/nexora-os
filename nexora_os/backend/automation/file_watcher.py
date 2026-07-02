"""
File Watcher Module
Monitors file system changes and triggers actions
"""
import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass(slots=True)
class FileWatch:
    """Represents a file watch configuration"""
    id: str
    path: str
    callback: Callable
    enabled: bool = True
    recursive: bool = False
    event_types: list[str] = None  # 'created', 'modified', 'deleted'
    
    def __post_init__(self):
        if self.event_types is None:
            self.event_types = ['created', 'modified']


class FileWatcher:
    """File system watcher"""
    
    def __init__(self, check_interval: float = 2.0) -> None:
        """
        Initialize file watcher
        
        Args:
            check_interval: Interval in seconds between checks
        """
        self.check_interval = check_interval
        self.watches: dict[str, FileWatch] = {}
        self._file_states: dict[str, dict] = {}
        self._running = False
        self._watcher_task: Optional[asyncio.Task] = None
    
    def add_watch(self, watch: FileWatch) -> bool:
        """
        Add a file watch
        
        Args:
            watch: File watch configuration
            
        Returns:
            True if added, False otherwise
        """
        if not os.path.exists(watch.path):
            return False
        
        self.watches[watch.id] = watch
        
        # Initialize file state
        if os.path.isfile(watch.path):
            self._file_states[watch.path] = {
                'mtime': os.path.getmtime(watch.path),
                'size': os.path.getsize(watch.path),
                'exists': True
            }
        elif os.path.isdir(watch.path):
            self._file_states[watch.path] = {
                'exists': True,
                'files': self._scan_directory(watch.path, watch.recursive)
            }
        
        return True
    
    def remove_watch(self, watch_id: str) -> bool:
        """
        Remove a file watch
        
        Args:
            watch_id: Watch ID
            
        Returns:
            True if removed, False otherwise
        """
        if watch_id in self.watches:
            watch = self.watches[watch_id]
            if watch.path in self._file_states:
                del self._file_states[watch.path]
            del self.watches[watch_id]
            return True
        return False
    
    def enable_watch(self, watch_id: str) -> bool:
        """Enable a watch"""
        if watch_id in self.watches:
            self.watches[watch_id].enabled = True
            return True
        return False
    
    def disable_watch(self, watch_id: str) -> bool:
        """Disable a watch"""
        if watch_id in self.watches:
            self.watches[watch_id].enabled = False
            return True
        return False
    
    def _scan_directory(self, path: str, recursive: bool = False) -> dict:
        """Scan directory and return file states"""
        files = {}
        if recursive:
            for root, dirs, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(root, filename)
                    files[filepath] = {
                        'mtime': os.path.getmtime(filepath),
                        'size': os.path.getsize(filepath)
                    }
        else:
            for item in os.listdir(path):
                filepath = os.path.join(path, item)
                if os.path.isfile(filepath):
                    files[filepath] = {
                        'mtime': os.path.getmtime(filepath),
                        'size': os.path.getsize(filepath)
                    }
        return files
    
    async def _check_file_changes(self, watch: FileWatch) -> None:
        """Check for file changes"""
        path = watch.path
        old_state = self._file_states.get(path)
        
        if not old_state:
            return
        
        if os.path.isfile(path):
            if not os.path.exists(path):
                if 'deleted' in watch.event_types:
                    await self._trigger_callback(watch, 'deleted', path)
                self._file_states[path]['exists'] = False
            else:
                new_mtime = os.path.getmtime(path)
                new_size = os.path.getsize(path)
                
                if old_state.get('exists', False) is False:
                    # File was recreated
                    if 'created' in watch.event_types:
                        await self._trigger_callback(watch, 'created', path)
                    self._file_states[path] = {
                        'mtime': new_mtime,
                        'size': new_size,
                        'exists': True
                    }
                elif new_mtime != old_state.get('mtime') or new_size != old_state.get('size'):
                    # File was modified
                    if 'modified' in watch.event_types:
                        await self._trigger_callback(watch, 'modified', path)
                    self._file_states[path] = {
                        'mtime': new_mtime,
                        'size': new_size,
                        'exists': True
                    }
        
        elif os.path.isdir(path):
            new_files = self._scan_directory(path, watch.recursive)
            old_files = old_state.get('files', {})
            
            # Check for new files
            for filepath, state in new_files.items():
                if filepath not in old_files:
                    if 'created' in watch.event_types:
                        await self._trigger_callback(watch, 'created', filepath)
            
            # Check for modified files
            for filepath, state in new_files.items():
                if filepath in old_files:
                    old_mtime = old_files[filepath].get('mtime')
                    old_size = old_files[filepath].get('size')
                    if state['mtime'] != old_mtime or state['size'] != old_size:
                        if 'modified' in watch.event_types:
                            await self._trigger_callback(watch, 'modified', filepath)
            
            # Check for deleted files
            for filepath in old_files:
                if filepath not in new_files:
                    if 'deleted' in watch.event_types:
                        await self._trigger_callback(watch, 'deleted', filepath)
            
            self._file_states[path] = {
                'exists': True,
                'files': new_files
            }
    
    async def _trigger_callback(self, watch: FileWatch, event_type: str, filepath: str) -> None:
        """Trigger the callback for a watch"""
        try:
            if asyncio.iscoroutinefunction(watch.callback):
                await watch.callback(event_type, filepath)
            else:
                watch.callback(event_type, filepath)
        except Exception as e:
            print(f"Error in file watch callback: {e}")
    
    async def _watcher_loop(self) -> None:
        """Main watcher loop"""
        while self._running:
            for watch in self.watches.values():
                if watch.enabled:
                    await self._check_file_changes(watch)
            await asyncio.sleep(self.check_interval)
    
    async def start(self) -> None:
        """Start the file watcher"""
        if not self._running:
            self._running = True
            self._watcher_task = asyncio.create_task(self._watcher_loop(), name="file_watcher")
    
    async def stop(self) -> None:
        """Stop the file watcher"""
        self._running = False
        if self._watcher_task:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
    
    def list_watches(self) -> list[dict[str, Any]]:
        """List all file watches"""
        return [
            {
                "id": watch.id,
                "path": watch.path,
                "enabled": watch.enabled,
                "recursive": watch.recursive,
                "event_types": watch.event_types
            }
            for watch in self.watches.values()
        ]


# Global file watcher instance
global_file_watcher = FileWatcher()


def add_file_watch(watch: FileWatch) -> bool:
    """Add a file watch using the global watcher"""
    return global_file_watcher.add_watch(watch)


async def start_file_watcher() -> None:
    """Start the global file watcher"""
    await global_file_watcher.start()


async def stop_file_watcher() -> None:
    """Stop the global file watcher"""
    await global_file_watcher.stop()
