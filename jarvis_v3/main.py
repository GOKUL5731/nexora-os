"""
JARVIS CORE OS — Main Entry Point
Usage:
  python main.py              → text chat
  python main.py --voice      → voice mode
  python main.py --gui        → full GUI dashboard (all phases)
  python main.py --setup      → first-time setup wizard
  python main.py --core-health → print system status JSON
"""

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.config import load_config, save_config, setup_logging

BANNER = r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
   Intelligent System v3.0 — Windows Edition
"""


async def setup_wizard():
    """First-time setup — collects API key and preferences."""
    print(BANNER)
    print("=" * 52)
    print("  FIRST-TIME SETUP")
    print("=" * 52)

    config = load_config()

    print("\nStep 1 - Local LLM Runtime")
    print("  JARVIS CORE OS is local-first. Cloud LLM setup is intentionally skipped.")
    config["llm"]["provider"] = "ollama"
    config["llm"]["model"] = input("Ollama reasoning model [llama3.2]: ").strip() or "llama3.2"
    config["llm"]["fallback_model"] = input("Fast fallback model [mistral]: ").strip() or "mistral"
    config["llm"]["coder_model"] = input("Coder model [deepseek-coder]: ").strip() or "deepseek-coder"
    config["llm"]["api_key"] = ""

    print("\nStep 2 — Voice Settings")
    print("  1. Piper (local offline, recommended)")
    print("  2. pyttsx3 (local offline fallback)")
    print("  3. edge-tts (network fallback)")
    tts = input("TTS backend [1]: ").strip() or "1"
    tts_map = {"1": "piper", "2": "pyttsx3", "3": "edge_tts"}
    config["voice"]["tts_backend"] = tts_map.get(tts, "piper")

    print("\nStep 3 — Android (optional)")
    ip = input("Phone IP for ADB (leave blank to skip): ").strip()
    if ip:
        config["android"]["device_id"] = f"{ip}:5555"

    save_config(config)
    print("\n✓ Config saved to config/config.json")
    print("✓ Run 'python main.py' to start JARVIS\n")


async def chat_mode(config: dict):
    """Interactive terminal chat."""
    from core.orchestrator import JARVISOrchestrator
    from self_learning.learning_engine import SelfLearningEngine

    jarvis   = JARVISOrchestrator(config)
    learning = SelfLearningEngine(config, jarvis.memory)

    # Start learning in background
    asyncio.create_task(learning.start())

    print(BANNER)
    print("=" * 52)
    print("  Type your command. 'help' for commands. 'exit' to quit.")
    print("=" * 52 + "\n")

    pending_id = None

    while True:
        try:
            user_in = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nJARVIS: Goodbye, Sir.")
            break

        if not user_in:
            continue

        # Built-in terminal commands
        if user_in.lower() in ("exit", "quit", "bye"):
            print("JARVIS: Goodbye, Sir.")
            break

        if user_in.lower() == "help":
            print("""
Commands:
  exit / quit    → Shutdown JARVIS
  status         → System info
  memory         → Show what JARVIS remembers
  learned        → Self-learning summary
  agents         → List loaded agents and tools
  android setup  → Android connection guide
""")
            continue

        if user_in.lower() == "status":
            from agents.system_agent import SystemAgent
            info = await SystemAgent(config).execute("get_system_info", {})
            print(f"JARVIS: CPU {info.get('cpu_percent','?')}% | "
                  f"RAM {info.get('ram_used_percent','?')}% of {info.get('ram_total_gb','?')}GB | "
                  f"OS: {info.get('os','?')}")
            continue

        if user_in.lower() == "memory":
            profile = jarvis.memory.get_user_profile()
            count   = jarvis.memory.get_interaction_count()
            print(f"JARVIS: I have {count} stored interactions.")
            if profile:
                print(f"  Profile: {profile}")
            continue

        if user_in.lower() == "learned":
            s = learning.get_summary()
            print(f"JARVIS: Learning summary:\n"
                  f"  Total interactions: {s['total_interactions']}\n"
                  f"  Strategies learned: {s['strategies_learned']}\n"
                  f"  Unresolved failures: {s['unresolved_failures']}")
            continue

        if user_in.lower() == "agents":
            tools  = jarvis.registry.list_tools()
            agents = jarvis.registry.list_agents()
            print(f"JARVIS: Loaded agents: {', '.join(agents)}")
            print(f"  Available tools ({len(tools)}): {', '.join(tools[:20])}{'...' if len(tools)>20 else ''}")
            continue

        # Handle pending confirmation
        if pending_id:
            fb = learning.detect_feedback(user_in)
            yes = any(w in user_in.lower() for w in ["yes","y","ok","confirm","சரி","sure"])
            no  = any(w in user_in.lower() for w in ["no","n","cancel","stop","வேண்டாம்"])
            if yes or no:
                resp = await jarvis.confirm_task(pending_id, yes)
                print(f"\nJARVIS: {resp.get('message','Done.')}\n")
                pending_id = None
                continue

        # Check for feedback on last response
        fb = learning.detect_feedback(user_in)
        if fb and jarvis.memory.get_ctx("last_task_id"):
            last_id = jarvis.memory.get_ctx("last_task_id")
            if fb == "positive":
                jarvis.memory.store_interaction(user_in, "acknowledged positive feedback",
                                                task_id=last_id, outcome="success")
                print("JARVIS: Glad that worked, Sir. I'll remember that approach.\n")
            else:
                print("JARVIS: Understood. Let me try again.\n")
                # Re-attempt original request
                orig = jarvis.memory.get_ctx("last_input", user_in)
                resp = await jarvis.process(f"Try again better: {orig}")
                print(f"\nJARVIS: {resp.get('message','')}\n")
            continue

        # Normal request
        resp = await jarvis.process(user_in)
        msg  = resp.get("message", "")

        if resp.get("type") == "confirmation_required":
            pending_id = resp.get("task_id")
            print(f"\nJARVIS: {msg}\n")
        else:
            pending_id = None
            print(f"\nJARVIS: {msg}\n")
            # Store context for feedback detection
            jarvis.memory.set_context("last_task_id", resp.get("task_id",""))
            jarvis.memory.set_context("last_input", user_in)


async def voice_mode(config: dict):
    """Voice-only mode — uses wake word."""
    from core.orchestrator import JARVISOrchestrator
    from agents.voice_agent import VoiceAgent

    jarvis = JARVISOrchestrator(config)
    voice  = VoiceAgent(config)

    print(BANNER)
    print(f"Voice mode active. Say '{config['voice']['wake_word'].upper()}' to activate.\n")
    await voice.speak("JARVIS online. Voice mode active.")

    cmd_q: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def on_wake(transcript: str):
        loop.call_soon_threadsafe(cmd_q.put_nowait, transcript)

    voice.start_wake_word(callback=on_wake)

    while True:
        transcript = await cmd_q.get()
        if not transcript or transcript in {"wake_word_detected", "__wake__"}:
            await voice.speak("Yes, Sir?")
            result = await voice.listen(timeout=12)
            transcript = result.get("text", "")

        if not transcript:
            await voice.speak("I didn't catch that.")
            continue

        print(f"You said: {transcript}")
        resp = await jarvis.process(transcript, context={"mode": "voice"})

        if resp.get("type") == "confirmation_required":
            await voice.speak(resp["message"])
            confirm_result = await voice.listen(timeout=10)
            confirm_text   = confirm_result.get("text","").lower()
            confirmed      = any(w in confirm_text for w in ["yes","ok","confirm","sure","சரி"])
            final = await jarvis.confirm_task(resp["task_id"], confirmed)
            await voice.speak(final.get("message","Done."))
        else:
            msg = resp.get("message","I'm not sure.")
            print(f"JARVIS: {msg}")
            await voice.speak(msg)


async def run_gui(config: dict):
    """Launch the full JARVIS CORE OS Dashboard with all phases."""
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    from jarvis_visual_core.core import JarvisVisualRuntime
    from jarvis_visual_core.ui import OrchestrationDashboard

    runtime = JarvisVisualRuntime(config)
    await runtime.start()
    startup = runtime.startup_diagnostics()
    if not startup["ok"]:
        print(
            "[WARN] Startup verification issues: "
            f"missing={startup['missing']} failed={len(startup['failed'])}"
        )

    win = OrchestrationDashboard(runtime)
    win.show()
    exit_code = app.exec()
    await runtime.shutdown()
    sys.exit(exit_code)


def run_debug_dashboard():
    """Launch the plain runtime debug dashboard."""
    from PySide6.QtWidgets import QApplication
    from ui.debug_dashboard import DebugDashboard
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    win = DebugDashboard()
    win.setWindowTitle("JARVIS Runtime Debug Dashboard")
    win.resize(1100, 720)
    win.show()
    sys.exit(app.exec())


def main():
    setup_logging("jarvis")
    parser = argparse.ArgumentParser(description="JARVIS CORE OS")
    parser.add_argument("--voice",  action="store_true", help="Voice mode")
    parser.add_argument("--gui",    action="store_true", help="Full GUI dashboard (all phases)")
    parser.add_argument("--setup",  action="store_true", help="First-time setup")
    parser.add_argument("--core-health", action="store_true", help="Print system health JSON")
    parser.add_argument("--debug-dashboard", action="store_true", help="Runtime infrastructure debug dashboard")
    args = parser.parse_args()

    config = load_config()

    if args.core_health:
        import json
        try:
            from core.jarvis_core_os import JarvisCoreOS
            core = JarvisCoreOS(config)
            print(json.dumps(core.health(), indent=2, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"status": "error", "error": str(e)}, indent=2))
    elif args.setup:
        asyncio.run(setup_wizard())
    elif args.voice:
        asyncio.run(voice_mode(config))
    elif args.gui:
        asyncio.run(run_gui(config))
    elif args.debug_dashboard:
        run_debug_dashboard()
    else:
        asyncio.run(chat_mode(config))


if __name__ == "__main__":
    main()
