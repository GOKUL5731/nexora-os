"""
JARVIS Phase 2 — Standalone Launcher
======================================
Launches JARVIS with Phase 2 deep learning layer integrated.

Usage:
    python jarvis_phase2.py            # GUI dashboard
    python jarvis_phase2.py --cli      # CLI with Phase 2
    python jarvis_phase2.py --test     # Run Phase 2 self-tests
    python jarvis_phase2.py --status   # Print Phase 2 status and exit
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.config import load_config, setup_logging

BANNER = r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗  ██████╗ ██████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝  ██╔══██╗╚════██╗
     ██║███████║██████╔╝██║   ██║██║███████╗  ██████╔╝ █████╔╝
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║  ██╔═══╝ ██╔═══╝
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║  ██║     ███████╗
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝  ╚═╝     ╚══════╝
   Deep Learning Intelligence Layer — Phase 2
"""


async def run_status():
    """Print Phase 2 status report."""
    print(BANNER)
    config = load_config()
    from core.phase2.phase2_core import JARVISPhase2
    p2     = JARVISPhase2(config)
    result = await p2.start(enable_gpu_monitor=False)
    print(json.dumps(result, indent=2, default=str))
    status = p2.get_status()
    print("\n── Full Status ──")
    print(json.dumps(status, indent=2, default=str))
    await p2.shutdown()


async def run_self_tests():
    """Execute Phase 2 self-tests for all modules."""
    print(BANNER)
    print("Running Phase 2 self-tests...\n")
    config  = load_config()
    results = {}

    # Test 1: GPU Manager
    print("[1/7] Testing GPU Manager...")
    try:
        from core.phase2.gpu_manager import GPUManager
        gm   = GPUManager()
        info = gm.get_gpu_info()
        safe = gm.is_training_safe()
        results["gpu_manager"] = {
            "status":  "PASS",
            "device":  info.get("name", "CPU"),
            "vram_mb": info.get("vram_total_mb", 0),
            "safe_to_train": safe["safe"],
        }
        gm.shutdown()
        print(f"   ✓ GPU Manager OK — device={info.get('name', 'CPU')}")
    except Exception as e:
        results["gpu_manager"] = {"status": "FAIL", "error": str(e)}
        print(f"   ✗ GPU Manager FAILED: {e}")

    # Test 2: CNN Engine
    print("[2/7] Testing CNN Vision Engine...")
    try:
        from core.phase2.cnn_engine import CNNVisionEngine
        cnn    = CNNVisionEngine(config)
        result = await cnn.analyze_screen()
        results["cnn_engine"] = {"status": "PASS", "scene": result.get("scene_summary", "ok")}
        cnn.shutdown()
        print(f"   ✓ CNN Engine OK — {result.get('scene_summary', 'analyzed')[:60]}")
    except Exception as e:
        results["cnn_engine"] = {"status": "FAIL", "error": str(e)}
        print(f"   ✗ CNN Engine FAILED: {e}")

    # Test 3: RNN Engine
    print("[3/7] Testing RNN Behavior Engine...")
    try:
        from core.phase2.rnn_engine import BehaviorRNN
        rnn = BehaviorRNN(config)
        rnn.record_command("test_command_1")
        rnn.record_command("test_command_2")
        rnn.record_command("test_command_3")
        pred  = rnn.predict_next()
        stats = rnn.get_stats()
        results["rnn_engine"] = {
            "status":     "PASS",
            "events":     stats["total_events"],
            "prediction": pred.get("top_command", "N/A"),
        }
        print(f"   ✓ RNN Engine OK — {stats['total_events']} events, prediction={pred.get('top_command', 'N/A')}")
    except Exception as e:
        results["rnn_engine"] = {"status": "FAIL", "error": str(e)}
        print(f"   ✗ RNN Engine FAILED: {e}")

    # Test 4: Multimodal Memory
    print("[4/7] Testing Multimodal Memory...")
    try:
        from core.phase2.multimodal_memory import MultimodalMemory
        mem = MultimodalMemory(config)
        rid = mem.store_text("Test memory entry for JARVIS Phase 2 self-test", category="test")
        mem.store_vision_event("test", "Self-test vision event", objects=["keyboard", "monitor"])
        results_search = mem.search("JARVIS test", top_k=3)
        stats = mem.get_memory_stats()
        results["multimodal_memory"] = {
            "status":     "PASS",
            "stored_id":  rid,
            "search_results": len(results_search),
            "stats":      stats,
        }
        print(f"   ✓ Memory OK — {stats['text_memories']} text, "
              f"{stats['vision_memories']} vision, "
              f"search returned {len(results_search)} results")
    except Exception as e:
        results["multimodal_memory"] = {"status": "FAIL", "error": str(e)}
        print(f"   ✗ Multimodal Memory FAILED: {e}")

    # Test 5: Self-Learning
    print("[5/7] Testing Self-Learning Engine...")
    try:
        from core.phase2.behavior_learning import SelfImprovementEngine
        sl = SelfImprovementEngine(config)
        sl.log_interaction("open_vscode", success=True, latency_ms=120, model_used="direct")
        sl.log_interaction("ask_ai",      success=True, latency_ms=800, model_used="llm")
        sl.log_interaction("unknown_cmd", success=False, latency_ms=500, model_used="llm")
        suggestion = sl.suggest_model("open vscode")
        summary    = sl.get_learning_summary()
        results["self_learning"] = {
            "status":     "PASS",
            "suggestion": suggestion,
            "summary":    summary,
        }
        print(f"   ✓ Self-Learning OK — "
              f"suggestion={suggestion['model']}, total={summary['total_interactions']}")
    except Exception as e:
        results["self_learning"] = {"status": "FAIL", "error": str(e)}
        print(f"   ✗ Self-Learning FAILED: {e}")

    # Test 6: Prediction Engine
    print("[6/7] Testing Prediction Engine...")
    try:
        from core.phase2.rnn_engine import BehaviorRNN
        from core.phase2.behavior_learning import SelfImprovementEngine
        from core.phase2.prediction_engine import PredictionEngine
        r  = BehaviorRNN(config)
        sl = SelfImprovementEngine(config)
        pe = PredictionEngine(r, sl, config)
        pred = pe.predict_next_action()
        timed = pe.get_timed_suggestions()
        cls   = pe.classify_command_type("analyze my screen with camera")
        results["prediction_engine"] = {
            "status":      "PASS",
            "predictions": len(pred.get("predictions", [])),
            "suggestions": len(timed),
            "cmd_type":    cls["type"],
        }
        print(f"   ✓ Prediction Engine OK — "
              f"type={cls['type']}, suggestions={len(timed)}")
    except Exception as e:
        results["prediction_engine"] = {"status": "FAIL", "error": str(e)}
        print(f"   ✗ Prediction Engine FAILED: {e}")

    # Test 7: Decision Engine
    print("[7/7] Testing Decision Engine...")
    try:
        from core.phase2.cnn_engine       import CNNVisionEngine
        from core.phase2.rnn_engine       import BehaviorRNN
        from core.phase2.behavior_learning import SelfImprovementEngine
        from core.phase2.multimodal_memory import MultimodalMemory
        from core.phase2.decision_engine  import DecisionEngine
        cnn  = CNNVisionEngine(config)
        rnn  = BehaviorRNN(config)
        sl   = SelfImprovementEngine(config)
        mem  = MultimodalMemory(config)
        de   = DecisionEngine(config, mem, cnn, rnn, sl)
        decision = await de.decide("open my coding project", use_screen=False)
        hints    = await de.get_proactive_suggestions()
        results["decision_engine"] = {
            "status":  "PASS",
            "handler": decision["routing"]["handler"],
            "hints":   len(hints),
            "mode":    decision["mode"],
        }
        cnn.shutdown()
        print(f"   ✓ Decision Engine OK — "
              f"handler={decision['routing']['handler']}, hints={len(hints)}")
    except Exception as e:
        results["decision_engine"] = {"status": "FAIL", "error": str(e)}
        print(f"   ✗ Decision Engine FAILED: {e}")

    # Summary
    print("\n" + "=" * 56)
    passed = sum(1 for r in results.values() if r.get("status") == "PASS")
    failed = len(results) - passed
    print(f"  PHASE 2 TEST RESULTS: {passed}/{len(results)} passed, {failed} failed")
    print("=" * 56)

    for name, r in results.items():
        status_sym = "✓" if r["status"] == "PASS" else "✗"
        print(f"  {status_sym} {name}: {r['status']}")

    if failed > 0:
        print(f"\n  {failed} test(s) failed. Check logs for details.")
        print("  Install missing dependencies:")
        print("    pip install torch torchvision ultralytics opencv-python")
        print("    pip install sentence-transformers pynvml matplotlib")

    return results


async def run_cli_phase2():
    """Interactive CLI with Phase 2 deep learning active."""
    print(BANNER)
    config = load_config()

    # Initialize Phase 2
    from core.phase2.phase2_core import JARVISPhase2
    p2 = JARVISPhase2(config)
    print("Initializing Phase 2 deep learning layer...")
    startup = await p2.start()
    print(f"Phase 2 Status: {startup.get('status', 'unknown')}")
    gpu = startup.get("gpu", {})
    if gpu.get("available"):
        print(f"GPU: {gpu.get('name', 'unknown')} | VRAM: {gpu.get('vram_total_mb', 0):.0f}MB")
    print()

    # Also initialize Phase 1 orchestrator
    try:
        from core.orchestrator import JARVISOrchestrator
        orc = JARVISOrchestrator(config)
    except Exception as e:
        print(f"Phase 1 orchestrator failed: {e}")
        orc = None

    print("JARVIS Phase 2 Online. Commands:")
    print("  'status'            → Phase 2 status")
    print("  'analyze screen'    → CNN screen analysis")
    print("  'detect objects'    → Object detection")
    print("  'presence'          → User presence check")
    print("  'train ...'         → Start/stop CNN training")
    print("  'predict next'      → LSTM behavior prediction")
    print("  'routine patterns'  → Show learned routines")
    print("  'remember ...'      → Store text memory")
    print("  'recall ...'        → Semantic memory search")
    print("  'exit'              → Quit\n")

    while True:
        try:
            cmd = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue
        if cmd.lower() in ("exit", "quit", "bye"):
            print("JARVIS Phase 2: Shutting down. Goodbye.")
            break

        if cmd.lower() == "status":
            status = p2.get_status()
            print(json.dumps(status, indent=2, default=str))
            continue

        # Try Phase 2 first
        result = await p2.process_command(cmd)
        msg    = result.get("message", "")

        if result.get("type") in ("context_enriched",) and orc:
            # Phase 2 routing to Phase 1
            ctx = {
                "phase2_context": result.get("phase2_data", {}),
                "memory_context": result.get("memory_context", ""),
                "mode":           result.get("mode", "normal"),
            }
            resp = await orc.process(cmd, context=ctx)
            msg  = resp.get("message", "I'm not sure how to help with that.")

        print(f"\nJARVIS: {msg}\n")

        # Log to Phase 2
        p2.log_command(cmd, success=True)

    await p2.shutdown()


async def run_gui():
    """Launch the JARVIS dashboard GUI with Phase 2."""
    config = load_config()

    # Initialize Phase 2 async
    from core.phase2.phase2_core import JARVISPhase2
    p2 = JARVISPhase2(config)
    await p2.start()

    # Launch GUI
    try:
        from PySide6.QtWidgets import QApplication
        from ui.dashboard import JARVISDashboard
        import sys

        app = QApplication.instance() or QApplication(sys.argv)

        from core.orchestrator import JARVISOrchestrator
        orc = JARVISOrchestrator(config)

        win = JARVISDashboard(
            orchestrator = orc,
            config       = config,
            memory       = orc.memory,
            plugins      = orc.plugin_mgr,
            phase2       = p2,
        )
        win.show()
        exit_code = app.exec()
        await p2.shutdown()
        sys.exit(exit_code)
    except ImportError as e:
        print(f"GUI requires PySide6: {e}")
        print("Falling back to CLI mode...")
        await run_cli_phase2()


def main():
    setup_logging("jarvis.phase2")
    parser = argparse.ArgumentParser(description="JARVIS Phase 2 — Deep Learning Layer")
    parser.add_argument("--cli",    action="store_true", help="Run CLI mode")
    parser.add_argument("--test",   action="store_true", help="Run self-tests")
    parser.add_argument("--status", action="store_true", help="Print status and exit")
    args = parser.parse_args()

    if args.test:
        asyncio.run(run_self_tests())
    elif args.status:
        asyncio.run(run_status())
    elif args.cli:
        asyncio.run(run_cli_phase2())
    else:
        asyncio.run(run_gui())


if __name__ == "__main__":
    main()
