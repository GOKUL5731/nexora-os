"""
Autonomous Task Executor Module
Executes tasks autonomously with application control and operation modification
"""
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class TaskStep:
    """Represents a single step in a task"""
    step_id: str
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = 3


@dataclass(slots=True)
class AutonomousTask:
    """Represents an autonomous task"""
    task_id: str
    name: str
    description: str
    steps: list[TaskStep] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    current_step: int = 0
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    result: dict[str, Any] = field(default_factory=dict)


class AutonomousExecutor:
    """Executor for autonomous tasks with application control"""
    
    def __init__(self) -> None:
        self.tasks: dict[str, AutonomousTask] = {}
        self._running = False
        self._executor_task: Optional[asyncio.Task] = None
        self._action_handlers: dict[str, Callable] = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """Register default action handlers"""
        from .application_launcher import global_app_launcher
        
        self._action_handlers = {
            "launch_app": lambda params: self._handle_launch_app(params),
            "terminate_app": lambda params: self._handle_terminate_app(params),
            "send_input": lambda params: self._handle_send_input(params),
            "wait": lambda params: self._handle_wait(params),
            "click": lambda params: self._handle_click(params),
            "type": lambda params: self._handle_type(params),
            "screenshot": lambda params: self._handle_screenshot(params),
            "ocr": lambda params: self._handle_ocr(params),
        }
    
    async def _handle_launch_app(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle application launch action"""
        from .application_launcher import global_app_launcher
        app_id = params.get("app_id")
        args = params.get("args")
        return await global_app_launcher.launch(app_id, args)
    
    async def _handle_terminate_app(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle application termination action"""
        from .application_launcher import global_app_launcher
        pid = params.get("pid")
        return await global_app_launcher.terminate(pid)
    
    async def _handle_send_input(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle sending input to application"""
        from .application_launcher import global_app_launcher
        pid = params.get("pid")
        input_text = params.get("text")
        return await global_app_launcher.send_input(pid, input_text)
    
    async def _handle_wait(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle wait action"""
        duration = params.get("duration", 1.0)
        await asyncio.sleep(duration)
        return {"ok": True, "message": f"Waited {duration} seconds"}
    
    async def _handle_click(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle mouse click action"""
        import pyautogui
        x = params.get("x")
        y = params.get("y")
        button = params.get("button", "left")
        
        try:
            pyautogui.click(x, y, button=button)
            return {"ok": True, "message": f"Clicked at ({x}, {y})"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_type(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle typing action"""
        import pyautogui
        text = params.get("text")
        interval = params.get("interval", 0.0)
        
        try:
            pyautogui.write(text, interval=interval)
            return {"ok": True, "message": f"Typed: {text}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_screenshot(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle screenshot action"""
        from PIL import ImageGrab
        import base64
        
        try:
            screenshot = ImageGrab.grab()
            import io
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            screenshot_base64 = base64.b64encode(buffer.getvalue()).decode()
            return {"ok": True, "screenshot": screenshot_base64}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    async def _handle_ocr(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle OCR action"""
        from PIL import ImageGrab
        import pytesseract
        
        try:
            screenshot = ImageGrab.grab()
            text = pytesseract.image_to_string(screenshot)
            return {"ok": True, "text": text}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def register_handler(self, action: str, handler: Callable) -> None:
        """Register a custom action handler"""
        self._action_handlers[action] = handler
    
    def create_task(
        self,
        task_id: str,
        name: str,
        description: str,
        steps: list[dict[str, Any]]
    ) -> AutonomousTask:
        """
        Create an autonomous task
        
        Args:
            task_id: Task identifier
            name: Task name
            description: Task description
            steps: List of step definitions
            
        Returns:
            Created task
        """
        task_steps = [
            TaskStep(
                step_id=step.get("step_id", f"step_{i}"),
                action=step.get("action"),
                parameters=step.get("parameters", {}),
                timeout=step.get("timeout", 30.0),
                max_retries=step.get("max_retries", 3)
            )
            for i, step in enumerate(steps)
        ]
        
        task = AutonomousTask(
            task_id=task_id,
            name=name,
            description=description,
            steps=task_steps
        )
        
        self.tasks[task_id] = task
        return task
    
    async def execute_task(self, task_id: str) -> dict[str, Any]:
        """
        Execute an autonomous task
        
        Args:
            task_id: Task identifier
            
        Returns:
            Execution result
        """
        if task_id not in self.tasks:
            return {"ok": False, "error": f"Task {task_id} not found"}
        
        task = self.tasks[task_id]
        
        if task.status == TaskStatus.RUNNING:
            return {"ok": False, "error": "Task is already running"}
        
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        
        for i, step in enumerate(task.steps):
            if task.status == TaskStatus.CANCELLED:
                break
            
            task.current_step = i
            
            # Execute step with retry logic
            for attempt in range(step.max_retries + 1):
                try:
                    handler = self._action_handlers.get(step.action)
                    
                    if not handler:
                        task.status = TaskStatus.FAILED
                        task.error = f"No handler for action: {step.action}"
                        return {"ok": False, "error": task.error}
                    
                    # Execute with timeout
                    result = await asyncio.wait_for(
                        handler(step.parameters),
                        timeout=step.timeout
                    )
                    
                    if result.get("ok"):
                        # Step succeeded
                        task.result[f"step_{i}"] = result
                        break
                    else:
                        # Step failed, retry
                        if attempt < step.max_retries:
                            step.retry_count += 1
                            await asyncio.sleep(1.0)
                        else:
                            task.status = TaskStatus.FAILED
                            task.error = result.get("error", "Step failed")
                            return {"ok": False, "error": task.error}
                
                except asyncio.TimeoutError:
                    if attempt < step.max_retries:
                        step.retry_count += 1
                        await asyncio.sleep(1.0)
                    else:
                        task.status = TaskStatus.FAILED
                        task.error = f"Step timeout after {step.timeout}s"
                        return {"ok": False, "error": task.error}
                
                except Exception as e:
                    if attempt < step.max_retries:
                        step.retry_count += 1
                        await asyncio.sleep(1.0)
                    else:
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        return {"ok": False, "error": task.error}
        
        # Task completed successfully
        task.status = TaskStatus.COMPLETED
        task.completed_at = time.time()
        
        return {
            "ok": True,
            "task_id": task_id,
            "message": "Task completed successfully",
            "result": task.result,
            "duration": task.completed_at - task.started_at
        }
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.CANCELLED
            return True
        return False
    
    def get_task_status(self, task_id: str) -> Optional[dict[str, Any]]:
        """Get task status"""
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        return {
            "task_id": task.task_id,
            "name": task.name,
            "description": task.description,
            "status": task.status.value,
            "current_step": task.current_step,
            "total_steps": len(task.steps),
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "error": task.error,
            "result": task.result
        }
    
    def list_tasks(self) -> list[dict[str, Any]]:
        """List all tasks"""
        return [self.get_task_status(task_id) for task_id in self.tasks.keys()]


# Global autonomous executor instance
global_autonomous_executor = AutonomousExecutor()


def create_autonomous_task(
    task_id: str,
    name: str,
    description: str,
    steps: list[dict[str, Any]]
) -> AutonomousTask:
    """Create an autonomous task using the global executor"""
    return global_autonomous_executor.create_task(task_id, name, description, steps)


async def execute_autonomous_task(task_id: str) -> dict[str, Any]:
    """Execute an autonomous task using the global executor"""
    return await global_autonomous_executor.execute_task(task_id)


def register_action_handler(action: str, handler: Callable) -> None:
    """Register an action handler using the global executor"""
    global_autonomous_executor.register_handler(action, handler)
