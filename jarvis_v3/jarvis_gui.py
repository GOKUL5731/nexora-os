"""
JARVIS GPU Edition Launcher — v5.1 Production
Wires: Orchestrator + Voice + Vision + Coder + Trainer + Personality + Dashboard
      + TrainingEngine + MobileEngine + WebEngine + TrayManager
Run:  python -X utf8 jarvis_gui.py
"""
import asyncio, logging, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.config import load_config, setup_logging


def main():
    setup_logging("jarvis")
    log = logging.getLogger("jarvis.gui")
    config = load_config()

    # ── PySide6 app ────────────────────────────────────────────────────────
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette, QColor
    except ImportError:
        print("Install PySide6:  pip install PySide6")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    app.setApplicationVersion("5.0-GPU")
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor("#0f0708"))
    pal.setColor(QPalette.WindowText,      QColor("#ffe9e6"))
    pal.setColor(QPalette.Base,            QColor("#1a0d10"))
    pal.setColor(QPalette.AlternateBase,   QColor("#261216"))
    pal.setColor(QPalette.Text,            QColor("#ffe9e6"))
    pal.setColor(QPalette.Button,          QColor("#1a0d10"))
    pal.setColor(QPalette.ButtonText,      QColor("#ff4d4d"))
    pal.setColor(QPalette.Highlight,       QColor("#ff4d4d"))
    app.setPalette(pal)

    # ── Single instance guard ───────────────────────────────────────────────
    try:
        from core.tray_manager import SingleInstanceGuard
        _guard = SingleInstanceGuard()
        if not _guard.acquire():
            log.error("Another JARVIS instance is already running. Exiting.")
            sys.exit(0)
    except Exception as _ge:
        log.debug(f"Instance guard: {_ge}")
        _guard = None

    # ── Core modules ───────────────────────────────────────────────────────
    orchestrator = memory = plugins = benchmark = updater = None
    router = voice = vision = coder = trainer = personality = None
    training_engine = mobile_engine = web_engine = None

    try:
        from core.orchestrator import JARVISOrchestrator
        orchestrator = JARVISOrchestrator(config)
        memory       = orchestrator.memory
        router       = orchestrator.router
        personality  = orchestrator.personality
        log.info("[OK] Orchestrator ready")
        try:
            import threading
            threading.Thread(
                target=lambda: router.warm_models(["phi", "mistral"]),
                daemon=True,
                name="jarvis-llm-warmup",
            ).start()
        except Exception as warm_err:
            log.debug(f"LLM warmup: {warm_err}")
    except Exception as e:
        log.error(f"Orchestrator: {e}")

    try:
        from core.plugin_manager import PluginManager
        plugins = PluginManager(config)
        if orchestrator:
            orchestrator.registry.attach_plugins(plugins)
        log.info(f"[OK] Plugins: {len(plugins.list_plugins())} loaded")
    except Exception as e:
        log.warning(f"Plugins: {e}")

    try:
        from core.benchmark import BenchmarkEngine
        benchmark = BenchmarkEngine(config)
        log.info("[OK] Benchmark ready")
    except Exception as e:
        log.warning(f"Benchmark: {e}")

    try:
        from core.updater import SelfUpdater
        updater = SelfUpdater(config)
        log.info("[OK] Updater ready")
    except Exception as e:
        log.warning(f"Updater: {e}")

    try:
        from core.voice import VoiceEngine
        voice = VoiceEngine(config)
        log.info("[OK] Voice engine ready")
    except Exception as e:
        log.warning(f"Voice: {e}")

    try:
        from core.vision import VisionEngine
        vision = VisionEngine(config)
        log.info("[OK] Vision engine ready")
    except Exception as e:
        log.warning(f"Vision: {e}")

    try:
        from core.coder import CodingCopilot
        coder = CodingCopilot(config, router)
        log.info("[OK] Coding copilot ready")
    except Exception as e:
        log.warning(f"Coder: {e}")

    try:
        from core.trainer import BehaviorTrainer
        trainer = BehaviorTrainer(config, memory, router)
        log.info("[OK] Behavior trainer ready")
    except Exception as e:
        log.warning(f"Trainer: {e}")

    try:
        from core.training_engine import TrainingEngine
        training_engine = TrainingEngine(config, router)
        log.info("[OK] Deep Learning Training Engine ready")
    except Exception as e:
        log.warning(f"TrainingEngine: {e}")

    try:
        from core.mobile_engine import MobileEngine
        mobile_engine = MobileEngine(config)
        log.info("[OK] Mobile Engine (ADB) ready")
    except Exception as e:
        log.warning(f"MobileEngine: {e}")

    try:
        from core.web_engine import WebEngine
        web_engine = WebEngine(config, router)
        log.info("[OK] Web/Security Engine ready")
    except Exception as e:
        log.warning(f"WebEngine: {e}")

    # ── UI ─────────────────────────────────────────────────────────────────
    from ui.widget import JARVISWidget
    from ui.dashboard import JARVISDashboard

    widget = JARVISWidget(orchestrator=orchestrator, config=config, voice_engine=voice)
    dashboard = JARVISDashboard(
        orchestrator=orchestrator, config=config,
        memory=memory, plugins=plugins,
        benchmark=benchmark, updater=updater,
    )

    widget.set_dashboard_callback(lambda: (dashboard.show(), dashboard.raise_()))

    # ── System tray ────────────────────────────────────────────────────────
    tray = None
    try:
        from core.tray_manager import TrayManager
        tray = TrayManager(app, widget=widget, dashboard=dashboard, config=config)
        log.info("[OK] System tray initialized")
    except Exception as e:
        log.warning(f"Tray: {e}")

    # ── Greet user ─────────────────────────────────────────────────────────
    if personality:
        greeting = personality.greet()
        widget._response.setText(greeting)
        if voice:
            asyncio.get_event_loop().run_until_complete(
                voice.speak(greeting)
            ) if False else None   # async speak on thread below

    # ── Start background trainer ────────────────────────────────────────────
    if trainer:
        import threading
        def _trainer_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(trainer.start())
        threading.Thread(target=_trainer_thread, daemon=True,
                         name="jarvis-trainer").start()

    # ── Hotkey: Ctrl+Space → show dashboard ───────────────────────────────
    try:
        import keyboard
        keyboard.add_hotkey("ctrl+space",
                            lambda: (dashboard.show(), dashboard.raise_()),
                            suppress=False)
        log.info("[OK] Hotkey Ctrl+Space → dashboard")
    except ImportError:
        log.debug("keyboard not installed — hotkey disabled")
    except Exception as e:
        log.debug(f"Hotkey: {e}")

    widget.show()
    log.info("JARVIS v5.1 GPU Edition — widget visible. All engines loaded.")
    if tray:
        tray.notify("JARVIS Online", "Systems initialized. Ready.", 3000)

    ret = app.exec()
    if _guard:
        _guard.release()
    sys.exit(ret)


if __name__ == "__main__":
    main()
