"""
JARVIS HUD Launcher — boots the animated 3D fullscreen HUD.
Run: python -X utf8 hud.py
Press Ctrl+Space for dashboard | Type to chat | ESC / double-click to quit
"""
import asyncio, logging, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.config import load_config, setup_logging


def main():
    setup_logging("jarvis")
    log = logging.getLogger("jarvis.hud")
    config = load_config()

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPalette, QColor

    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS HUD")
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#00040f"))
    app.setPalette(pal)

    # ── Load core ──────────────────────────────────────────────────────────
    orchestrator = None
    try:
        from core.orchestrator import JARVISOrchestrator
        orchestrator = JARVISOrchestrator(config)
        log.info("[OK] Orchestrator")
    except Exception as e:
        log.error(f"Orchestrator: {e}")

    try:
        from core.plugin_manager import PluginManager
        plugins = PluginManager(config)
        if orchestrator:
            orchestrator.registry.attach_plugins(plugins)
        log.info(f"[OK] Plugins: {len(plugins.list_plugins())}")
    except Exception as e:
        log.warning(f"Plugins: {e}")

    # ── Launch HUD ─────────────────────────────────────────────────────────
    from ui.jarvis_hud import JarvisHUD
    hud = JarvisHUD(orchestrator=orchestrator, config=config)
    hud.show()

    # ── Dashboard on Ctrl+Space ────────────────────────────────────────────
    try:
        from ui.dashboard import JARVISDashboard
        from core.benchmark import BenchmarkEngine
        from core.updater import SelfUpdater
        bench  = BenchmarkEngine(config)
        updater = SelfUpdater(config)
        mem    = orchestrator.memory if orchestrator else None
        dashboard = JARVISDashboard(
            orchestrator=orchestrator, config=config,
            memory=mem, plugins=plugins if 'plugins' in dir() else None,
            benchmark=bench, updater=updater,
        )
        try:
            import keyboard
            keyboard.add_hotkey("ctrl+space",
                lambda: (dashboard.show(), dashboard.raise_()))
            log.info("[OK] Ctrl+Space → dashboard")
        except ImportError:
            pass
    except Exception as e:
        log.warning(f"Dashboard: {e}")

    # ── Behavior trainer background ────────────────────────────────────────
    try:
        from core.trainer import BehaviorTrainer
        from core.llm_router import LLMRouter
        router  = LLMRouter(config)
        trainer = BehaviorTrainer(config, orchestrator.memory, router)
        import threading
        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(trainer.start())
        threading.Thread(target=_run, daemon=True, name="jarvis-trainer").start()
        log.info("[OK] Trainer started")
    except Exception as e:
        log.warning(f"Trainer: {e}")

    log.info("JARVIS 3D HUD active. Type to chat. ESC to exit.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
