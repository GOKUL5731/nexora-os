import sys
import asyncio
import psutil
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QApplication
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QColor

from ui.theme import Theme, STYLESHEET
from ui.sidebar import Sidebar
from ui.ai_core import AICoreWidget
from ui.system_panel import SystemPanel
from ui.voice_panel import VoicePanel
from ui.system_control import SystemControlPanel
from ui.workflow_panel import WorkflowPanel


class AsyncCommandWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, orchestrator, voice_engine, command: str):
        super().__init__()
        self.orchestrator = orchestrator
        self.voice_engine = voice_engine
        self.command = command

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.orchestrator.process(self.command))
            if self.voice_engine and result.get("message"):
                loop.run_until_complete(self.voice_engine.speak(result["message"]))
            loop.close()
            self.done.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class WorkflowRunWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, workflow_engine, name: str):
        super().__init__()
        self.workflow_engine = workflow_engine
        self.name = name

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.workflow_engine.run(self.name))
            loop.close()
            self.done.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class VoiceInteractionWorker(QThread):
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, orchestrator, voice_engine):
        super().__init__()
        self.orchestrator = orchestrator
        self.voice_engine = voice_engine

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.voice_engine.speak("Yes, Sir?"))
            heard = loop.run_until_complete(self.voice_engine.listen(timeout=12))
            text = heard.get("text", "")
            if not text:
                loop.run_until_complete(self.voice_engine.speak("I did not catch that."))
                self.done.emit({"message": "No speech detected", "heard": heard})
                loop.close()
                return
            result = loop.run_until_complete(self.orchestrator.process(text, context={"mode": "voice"}))
            if result.get("message"):
                loop.run_until_complete(self.voice_engine.speak(result["message"]))
            loop.close()
            result["heard"] = heard
            self.done.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))

class JARVISDashboard(QMainWindow):
    def __init__(
        self, orchestrator=None, config: dict = None, memory=None, plugins=None,
        benchmark=None, updater=None, phase2=None, voice_engine=None,
        workflow_engine=None, agent_manager=None, module_manager=None,
        health_monitor=None,
    ):
        super().__init__()
        
        # Original references
        self.orc = orchestrator
        self.cfg = config or {}
        self.mem = memory
        self.plug = plugins
        self.bench = benchmark
        self.upd = updater
        self.p2 = phase2
        self.voice_engine = voice_engine
        self.workflow_engine = workflow_engine
        self.agent_manager = agent_manager
        self.module_manager = module_manager
        self.health_monitor = health_monitor
        try:
            from core.event_bus import get_event_bus
            self.bus = get_event_bus()
        except Exception:
            self.bus = None
        self._workers = []
        
        self._setup_window()
        self._build_ui()
        self._connect_backend()
        self._start_timers()

    def _setup_window(self):
        self.setWindowTitle("JARVIS — Cinematic UI")
        self.resize(1400, 850)
        self.setStyleSheet(STYLESHEET)
        
        # Set dark background palette
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(Theme.BG_DARK))
        self.setPalette(palette)

    def _build_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Top section: Sidebar + AICore + SystemPanel
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(10, 10, 10, 10)
        top_layout.setSpacing(10)
        
        self.sidebar = Sidebar()
        self.ai_core = AICoreWidget()
        self.system_panel = SystemPanel()
        
        top_layout.addWidget(self.sidebar)
        top_layout.addWidget(self.ai_core, 1) # Give AI core more space
        top_layout.addWidget(self.system_panel)
        
        main_layout.addLayout(top_layout, 2)
        
        # Bottom section: 3 panels
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(10, 0, 10, 10)
        bottom_layout.setSpacing(10)
        
        self.voice_panel = VoicePanel()
        self.system_control = SystemControlPanel()
        self.workflow_panel = WorkflowPanel()
        
        # Make them share space
        bottom_layout.addWidget(self.voice_panel, 1)
        bottom_layout.addWidget(self.system_control, 1)
        bottom_layout.addWidget(self.workflow_panel, 1)
        
        main_layout.addLayout(bottom_layout, 1)

    def _connect_backend(self):
        self.system_control.command_submitted.connect(self._run_command)
        self.system_control.action_requested.connect(self._run_action)
        self.workflow_panel.run_requested.connect(self._run_workflow)
        if self.voice_engine:
            try:
                self.voice_engine.start_wake_word(callback=self._on_voice_command)
            except Exception as exc:
                self.append_log(f"Voice wake listener failed: {exc}")

    def _start_timers(self):
        self.sys_timer = QTimer(self)
        self.sys_timer.timeout.connect(self._update_system_stats)
        self.sys_timer.start(2000)

        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self._update_backend_state)
        self.state_timer.start(500)

    def _update_system_stats(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        storage = psutil.disk_usage('/').percent
        
        gpu = 0
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu = util.gpu
        except Exception:
            gpu = 0
            
        self.system_panel.update_system_stats(cpu, ram, gpu, storage)

    def _update_backend_state(self):
        if self.health_monitor:
            try:
                self.health_monitor.snapshot()
            except Exception:
                pass
        if not self.bus:
            return
        state = self.bus.state_snapshot()
        self.voice_panel.update_voice_state(state.get("voice", {}), state.get("audio", {}))
        voice = state.get("voice", {})
        self.ai_core.set_listening(bool(voice.get("listening") or voice.get("speaking")))
        if hasattr(self.ai_core, "subtitle"):
            task = state.get("current_task", {})
            if task.get("status") == "started":
                self.ai_core.subtitle.setText("Working...")
            elif voice.get("speaking"):
                self.ai_core.subtitle.setText("Speaking")
            elif voice.get("listening"):
                self.ai_core.subtitle.setText("Listening")
            else:
                self.ai_core.subtitle.setText("How can I help you, Gokul?")
        self.system_panel.update_modules(state.get("modules", []))
        self.workflow_panel.update_workflows(state.get("workflows", []), state.get("running_workflows", []))
        logs = self.bus.history(limit=3, topic_prefix="log.")
        self.system_panel.update_diagnostics(state.get("health", {}), logs)

    def set_listening_state(self, is_listening):
        self.ai_core.set_listening(is_listening)
        if is_listening:
            self.voice_panel.status.setText("Listening...")
            self.voice_panel.status.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        else:
            self.voice_panel.status.setText("Processing...")
            self.voice_panel.status.setStyleSheet(f"color: {Theme.TEXT_MUTED};")

    def append_log(self, text: str):
        self.workflow_panel.append_log(text)

    def _run_command(self, command: str):
        if not self.orc:
            self.append_log("Orchestrator unavailable.")
            return
        self.append_log(f"> {command}")
        worker = AsyncCommandWorker(self.orc, self.voice_engine, command)
        worker.done.connect(lambda result: self._command_done(worker, result))
        worker.error.connect(lambda error: self._worker_error(worker, error))
        self._workers.append(worker)
        worker.start()

    def _run_action(self, action: str):
        command_map = {
            "Applications": "open applications folder",
            "Files": "open file explorer",
            "Terminal": "open terminal",
            "Settings": "open settings",
            "Devices": "show connected devices",
            "Network": "show network status",
            "Clipboard": "read clipboard",
            "Tasks": "system status",
        }
        command = command_map.get(action)
        if command:
            self._run_command(command)
        else:
            self.append_log(f"{action} requires confirmation from the command line.")

    def _run_workflow(self, name: str):
        if not self.workflow_engine:
            self.append_log("Workflow engine unavailable.")
            return
        self.append_log(f"Running workflow: {name}")
        worker = WorkflowRunWorker(self.workflow_engine, name)
        worker.done.connect(lambda result: self._workflow_done(worker, result))
        worker.error.connect(lambda error: self._worker_error(worker, error))
        self._workers.append(worker)
        worker.start()

    def _on_voice_command(self, transcript: str):
        if transcript in {"__wake__", "wake_word_detected", ""}:
            if self.voice_engine:
                self.voice_engine._listening = False
                worker = VoiceInteractionWorker(self.orc, self.voice_engine)
                worker.done.connect(lambda result: (self._command_done(worker, result), self._restart_wake_listener()))
                worker.error.connect(lambda error: (self._worker_error(worker, error), self._restart_wake_listener()))
                self._workers.append(worker)
                worker.start()
            return
        self._run_command(transcript)

    def _command_done(self, worker, result: dict):
        self.append_log(result.get("message", str(result)))
        self._cleanup_worker(worker)

    def _workflow_done(self, worker, result: dict):
        self.append_log(f"Workflow {result.get('workflow')} finished: {result.get('status')}")
        self._cleanup_worker(worker)

    def _worker_error(self, worker, error: str):
        self.append_log(f"Error: {error}")
        self._cleanup_worker(worker)

    def _cleanup_worker(self, worker):
        if worker in self._workers:
            self._workers.remove(worker)

    def _restart_wake_listener(self):
        if self.voice_engine:
            try:
                self.voice_engine.start_wake_word(callback=self._on_voice_command)
            except Exception:
                pass

    def closeEvent(self, event):
        if self.voice_engine:
            self.voice_engine.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JARVISDashboard()
    window.show()
    sys.exit(app.exec())
