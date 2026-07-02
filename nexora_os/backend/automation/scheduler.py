"""
Task Scheduler Module
Handles scheduled task execution with cron-like functionality
"""
import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional


@dataclass(slots=True)
class ScheduledTask:
    """Represents a scheduled task"""
    id: str
    name: str
    task_func: Callable
    schedule: str  # Cron-like schedule (e.g., "0 * * * *" for every hour)
    enabled: bool = True
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0


class TaskScheduler:
    """Scheduler for executing tasks on schedule"""
    
    def __init__(self) -> None:
        self.tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
    
    def add_task(
        self,
        task_id: str,
        name: str,
        task_func: Callable,
        schedule: str,
        enabled: bool = True
    ) -> None:
        """
        Add a scheduled task
        
        Args:
            task_id: Unique task identifier
            name: Task name
            task_func: Function to execute
            schedule: Cron-like schedule (minute hour day month weekday)
            enabled: Whether task is enabled
        """
        task = ScheduledTask(
            id=task_id,
            name=name,
            task_func=task_func,
            schedule=schedule,
            enabled=enabled
        )
        self.tasks[task_id] = task
        self._calculate_next_run(task)
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            return True
        return False
    
    def enable_task(self, task_id: str) -> bool:
        """Enable a task"""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = True
            self._calculate_next_run(self.tasks[task_id])
            return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """Disable a task"""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = False
            return True
        return False
    
    def _calculate_next_run(self, task: ScheduledTask) -> None:
        """Calculate next run time based on schedule"""
        # Simple implementation: parse basic schedules
        # Format: "minute hour day month weekday"
        # Supports: "*" (any), "*/n" (every n), specific numbers
        
        parts = task.schedule.split()
        if len(parts) != 5:
            # Invalid schedule, default to 1 hour
            task.next_run = time.time() + 3600
            return
        
        minute, hour, day, month, weekday = parts
        
        now = datetime.now()
        next_run = now + timedelta(hours=1)  # Default: 1 hour from now
        
        # Simple parsing for common schedules
        if minute == "*" and hour == "*":
            # Every minute
            next_run = now + timedelta(minutes=1)
        elif minute == "*/5" and hour == "*":
            # Every 5 minutes
            next_run = now + timedelta(minutes=5)
        elif minute == "*/15" and hour == "*":
            # Every 15 minutes
            next_run = now + timedelta(minutes=15)
        elif minute == "*/30" and hour == "*":
            # Every 30 minutes
            next_run = now + timedelta(minutes=30)
        elif minute == "0" and hour == "*":
            # Every hour
            next_run = now + timedelta(hours=1)
        elif minute == "0" and hour == "*/6":
            # Every 6 hours
            next_run = now + timedelta(hours=6)
        elif minute == "0" and hour == "*/12":
            # Every 12 hours
            next_run = now + timedelta(hours=12)
        elif minute == "0" and hour == "0":
            # Daily at midnight
            next_run = now + timedelta(days=1)
            next_run = next_run.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            # Try to parse specific time
            try:
                target_hour = int(hour) if hour != "*" else now.hour
                target_minute = int(minute) if minute != "*" else 0
                next_run = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
            except ValueError:
                next_run = now + timedelta(hours=1)
        
        task.next_run = next_run.timestamp()
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop"""
        while self._running:
            now = time.time()
            
            for task in self.tasks.values():
                if not task.enabled:
                    continue
                
                if task.next_run and now >= task.next_run:
                    try:
                        # Execute the task
                        if asyncio.iscoroutinefunction(task.task_func):
                            await task.task_func()
                        else:
                            task.task_func()
                        
                        task.last_run = now
                        task.run_count += 1
                        self._calculate_next_run(task)
                    except Exception as e:
                        print(f"Error executing task {task.name}: {e}")
            
            # Sleep for 10 seconds before next check
            await asyncio.sleep(10)
    
    async def start(self) -> None:
        """Start the scheduler"""
        if not self._running:
            self._running = True
            self._scheduler_task = asyncio.create_task(self._scheduler_loop(), name="task_scheduler")
    
    async def stop(self) -> None:
        """Stop the scheduler"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
    
    def get_task_status(self, task_id: str) -> Optional[dict[str, Any]]:
        """Get status of a specific task"""
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        return {
            "id": task.id,
            "name": task.name,
            "schedule": task.schedule,
            "enabled": task.enabled,
            "last_run": task.last_run,
            "next_run": task.next_run,
            "run_count": task.run_count
        }
    
    def list_tasks(self) -> list[dict[str, Any]]:
        """List all scheduled tasks"""
        return [self.get_task_status(task_id) for task_id in self.tasks.keys()]


# Global scheduler instance
global_scheduler = TaskScheduler()


def schedule_task(
    task_id: str,
    name: str,
    task_func: Callable,
    schedule: str,
    enabled: bool = True
) -> None:
    """Schedule a task on the global scheduler"""
    global_scheduler.add_task(task_id, name, task_func, schedule, enabled)


async def start_scheduler() -> None:
    """Start the global scheduler"""
    await global_scheduler.start()


async def stop_scheduler() -> None:
    """Stop the global scheduler"""
    await global_scheduler.stop()
