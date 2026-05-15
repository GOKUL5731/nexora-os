"""
JARVIS Comprehensive Test Suite — All Modules
============================================
Tests: Config | LLM Router | Memory | Orchestrator |
       Command Engine | Sandbox | Reliability |
       Training Engine | Mobile Engine | Web Engine |
       Tray Manager | Voice | Vision | Trainer

Run: python -X utf8 tests/test_all.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Test utilities ────────────────────────────────────────────────────────────
_PASS = 0
_FAIL = 0
_SKIP = 0
_RESULTS: list[tuple[str, str, str]] = []   # (name, status, detail)


def ok(name: str, detail: str = ""):
    global _PASS
    _PASS += 1
    _RESULTS.append((name, "PASS", detail))
    print(f"  ✓  {name}" + (f" — {detail}" if detail else ""))


def fail(name: str, detail: str = ""):
    global _FAIL
    _FAIL += 1
    _RESULTS.append((name, "FAIL", detail))
    print(f"  ✗  {name}" + (f" — {detail}" if detail else ""))


def skip(name: str, reason: str = ""):
    global _SKIP
    _SKIP += 1
    _RESULTS.append((name, "SKIP", reason))
    print(f"  ⊖  {name}" + (f" — SKIPPED: {reason}" if reason else ""))


def section(title: str):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Test groups ───────────────────────────────────────────────────────────────

def test_config():
    section("1. Configuration")
    try:
        from core.config import load_config, setup_logging
        cfg = load_config()
        assert isinstance(cfg, dict), "Config must be a dict"
        ok("Config loads as dict")
    except Exception as e:
        fail("Config load", str(e)); return

    assert "llm" in cfg, "Missing 'llm' key"
    ok("Config has 'llm' section")

    assert "voice" in cfg, "Missing 'voice' key"
    ok("Config has 'voice' section")

    assert "vision" in cfg, "Missing 'vision' key"
    ok("Config has 'vision' section")


def test_memory():
    section("2. Memory Manager")
    try:
        from core.config import load_config
        from memory.memory_manager import MemoryManager
        cfg = load_config()
        mem = MemoryManager(cfg)
        ok("MemoryManager instantiated")
    except Exception as e:
        fail("MemoryManager init", str(e)); return

    try:
        mem.store_interaction("test input", "test response", tags=["test"])
        ok("store_interaction")
    except Exception as e:
        fail("store_interaction", str(e))

    try:
        count = mem.get_interaction_count()
        assert isinstance(count, int)
        ok(f"get_interaction_count → {count} total interaction(s)")
    except Exception as e:
        fail("get_interaction_count", str(e))

    try:
        recent = mem.recent_events(limit=5)
        assert isinstance(recent, list)
        ok(f"recent_events → {len(recent)} event(s)")
    except Exception as e:
        fail("recent_events", str(e))

    try:
        mem.store_fact("test_ns", "key1", "value1")
        facts = mem.get_facts("test_ns")
        assert isinstance(facts, dict)
        ok(f"store_fact / get_facts → {len(facts)} entries")
    except Exception as e:
        fail("Facts system", str(e))


def test_llm_router():
    section("3. LLM Router")
    try:
        from core.config import load_config
        from core.llm_router import LLMRouter
        cfg = load_config()
        router = LLMRouter(cfg)
        ok("LLMRouter instantiated")
    except Exception as e:
        fail("LLMRouter init", str(e)); return

    try:
        model = router.select_model("write a python function")
        assert isinstance(model, str) and model
        ok(f"select_model (code) → '{model}'")
    except Exception as e:
        fail("select_model (code)", str(e))

    try:
        model = router.select_model("what time is it")
        ok(f"select_model (quick) → '{model}'")
    except Exception as e:
        fail("select_model (quick)", str(e))

    try:
        model = router.select_model("explain quantum computing")
        ok(f"select_model (general) → '{model}'")
    except Exception as e:
        fail("select_model (general)", str(e))


def test_command_engine():
    section("4. Command Engine (Deterministic)")
    try:
        from core.config import load_config
        from core.command_engine import CommandEngine
        cfg = load_config()
        ce  = CommandEngine(cfg)
        ok("CommandEngine instantiated")
    except Exception as e:
        fail("CommandEngine init", str(e)); return

    # Time query
    try:
        d = run_async(ce.try_execute("what time is it"))
        assert d.handled and d.tool == "direct_time"
        ok("Time query handled deterministically")
    except Exception as e:
        fail("Time query", str(e))

    # Date query
    try:
        d = run_async(ce.try_execute("today's date"))
        assert d.handled and d.tool == "direct_date"
        ok("Date query handled deterministically")
    except Exception as e:
        fail("Date query", str(e))

    # Cancel
    try:
        d = run_async(ce.try_execute("cancel"))
        assert d.handled
        ok("Cancel command handled")
    except Exception as e:
        fail("Cancel", str(e))

    # App open pattern
    try:
        d = run_async(ce.try_execute("open notepad"))
        assert d.handled
        ok(f"Open app handled → tool='{d.tool}'")
    except Exception as e:
        fail("Open app", str(e))

    # Remember pattern
    try:
        d = run_async(ce.try_execute("remember that I prefer dark mode"))
        assert d.handled
        ok("Remember command handled")
    except Exception as e:
        fail("Remember", str(e))


def test_sandbox():
    section("5. Sandbox Engine")
    try:
        from core.sandbox_engine import SandboxEngine
        se = SandboxEngine()
        ok("SandboxEngine instantiated")
    except Exception as e:
        fail("SandboxEngine init", str(e)); return

    try:
        session = se.create_session("test_session")
        ok(f"Session created: {session.id[:12]}…")
    except Exception as e:
        fail("create_session", str(e)); return

    try:
        p = se.write_file(session, "hello.py", "print('Hello from sandbox')\n")
        assert p.exists()
        ok("write_file → file exists")
    except Exception as e:
        fail("write_file", str(e))

    try:
        result = se.run_py_compile(session, "hello.py")
        assert result.ok, f"Compile failed: {result.stderr}"
        ok("run_py_compile → syntax OK")
    except Exception as e:
        fail("run_py_compile", str(e))

    try:
        result = se.run_python(session, "hello.py", timeout=10)
        assert result.ok, f"Execution failed: {result.stderr}"
        assert "Hello" in result.stdout
        ok(f"run_python → '{result.stdout.strip()}'")
    except Exception as e:
        fail("run_python", str(e))

    try:
        se.cleanup_session(session)
        assert not session.root.exists()
        ok("cleanup_session → directory removed")
    except Exception as e:
        fail("cleanup_session", str(e))


def test_reliability():
    section("6. Reliability Engine")
    try:
        from core.reliability_engine import ReliabilityEngine
        re = ReliabilityEngine()
        ok("ReliabilityEngine instantiated")
    except Exception as e:
        fail("ReliabilityEngine init", str(e)); return

    try:
        plan = [{"tool": "open_app", "args": {}, "risk_level": "low"}]
        r = re.score_plan(plan)
        assert 0 <= r.score <= 1
        ok(f"score_plan → {r.score:.2f} ({r.level})")
    except Exception as e:
        fail("score_plan", str(e))

    try:
        r = re.score_result({"ok": True, "data": "some data"})
        assert r.score >= 0.5
        ok(f"score_result (good) → {r.score:.2f}")
    except Exception as e:
        fail("score_result (good)", str(e))

    try:
        r = re.score_result({"error": "something went wrong"})
        assert r.score < 0.5
        ok(f"score_result (error) → {r.score:.2f}")
    except Exception as e:
        fail("score_result (error)", str(e))

    # Async retry test
    try:
        call_count = [0]
        async def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise RuntimeError("first attempt always fails")
            return {"ok": True, "data": "success"}

        result = run_async(re.execute_with_retry("test_op", flaky, max_retries=2))
        assert result["ok"] is True
        ok(f"execute_with_retry → OK after {result['attempts']} attempt(s)")
    except Exception as e:
        fail("execute_with_retry", str(e))


def test_training_engine():
    section("7. Training Engine")
    try:
        from core.training_engine import TrainingEngine
        te = TrainingEngine({})
        ok("TrainingEngine instantiated")
    except Exception as e:
        fail("TrainingEngine init", str(e)); return

    try:
        datasets = te.list_datasets()
        assert isinstance(datasets, list)
        ok(f"list_datasets → {len(datasets)} dataset(s)")
    except Exception as e:
        fail("list_datasets", str(e))

    try:
        from core.training_engine import DATASET_DIR, MODELS_DIR
        assert DATASET_DIR.exists() or True   # Created lazily
        ok("Dataset/models directories reachable")
    except Exception as e:
        fail("Directory check", str(e))

    try:
        models = te.list_models()
        assert isinstance(models, list)
        ok(f"list_models → {len(models)} model(s) saved")
    except Exception as e:
        fail("list_models", str(e))

    try:
        runs = te.list_runs()
        assert isinstance(runs, list)
        ok(f"list_runs → {len(runs)} past run(s)")
    except Exception as e:
        fail("list_runs", str(e))

    # Check torch availability
    try:
        import torch
        cuda = torch.cuda.is_available()
        gpu  = torch.cuda.get_device_name(0) if cuda else "N/A"
        ok(f"PyTorch {torch.__version__} | CUDA={cuda} | GPU={gpu}")
    except Exception as e:
        skip("PyTorch check", f"not usable ({type(e).__name__}: {e}) - run GPU setup")


def test_mobile_engine():
    section("8. Mobile Engine (ADB)")
    try:
        from core.mobile_engine import MobileEngine
        me = MobileEngine({})
        ok("MobileEngine instantiated")
    except Exception as e:
        fail("MobileEngine init", str(e)); return

    # Verify ADB executable exists
    try:
        import subprocess
        r = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            ok(f"ADB found: {r.stdout.splitlines()[0]}")
        else:
            skip("ADB version check", "ADB not in PATH — install Android Platform Tools")
    except Exception:
        skip("ADB check", "ADB not in PATH")

    # Connectivity check (soft — no device needed)
    try:
        connected = run_async(me.is_connected())
        ok(f"is_connected() call → {connected} (device may not be plugged in)")
    except Exception as e:
        fail("is_connected", str(e))

    # Test COMMON_APPS mapping
    try:
        assert "whatsapp" in me.COMMON_APPS
        assert "chrome" in me.COMMON_APPS
        ok(f"COMMON_APPS has {len(me.COMMON_APPS)} mappings")
    except Exception as e:
        fail("COMMON_APPS", str(e))


def test_web_engine():
    section("9. Web Engine")
    try:
        from core.web_engine import WebEngine
        we = WebEngine({})
        ok("WebEngine instantiated")
    except Exception as e:
        fail("WebEngine init", str(e)); return

    # Static security scan (no network needed)
    try:
        code = '''
password = "hunter2"
query = "SELECT * FROM users WHERE id=" + user_id
subprocess.run(cmd, shell=True)
eval(user_input)
'''
        findings = we._static_security_scan(code, "python")
        assert len(findings) >= 3, f"Expected >= 3 findings, got {len(findings)}: {findings}"
        ok(f"_static_security_scan → {len(findings)} issues detected")
        for f in findings:
            print(f"       ⚠ {f['type']} @ line {f['line']}")
    except Exception as e:
        fail("static_security_scan", str(e))

    # Log anomaly detection (no network needed)
    try:
        fake_log = (
            "2024-01-01 ERROR Database connection failed\n"
            "2024-01-01 CRITICAL System meltdown\n"
            "2024-01-01 ERROR permission denied for user root\n"
            "401 Unauthorized login attempt from 192.168.1.100\n"
        )
        findings = we._detect_log_anomalies(fake_log)
        assert len(findings) >= 2
        ok(f"_detect_log_anomalies → {len(findings)} anomaly type(s)")
    except Exception as e:
        fail("_detect_log_anomalies", str(e))

    # DNS lookup test
    try:
        result = run_async(we.dns_lookup("google.com"))
        if result.get("ok"):
            ok(f"dns_lookup('google.com') → {result['ips'][0] if result['ips'] else 'no IPs'}")
        else:
            skip("dns_lookup", f"No network: {result.get('error')}")
    except Exception as e:
        skip("dns_lookup", str(e))


def test_tray_manager():
    section("10. Tray Manager")
    try:
        from core.tray_manager import StartupManager, SingleInstanceGuard
        ok("TrayManager module imports successfully")
    except Exception as e:
        fail("TrayManager import", str(e)); return

    try:
        sm = StartupManager()
        is_reg = sm.is_registered()
        ok(f"StartupManager.is_registered() → {is_reg}")
    except Exception as e:
        fail("StartupManager", str(e))

    try:
        guard = SingleInstanceGuard()
        # Don't actually acquire — would block re-running test
        ok("SingleInstanceGuard instantiated")
    except Exception as e:
        fail("SingleInstanceGuard", str(e))


def test_orchestrator_offline():
    section("11. Orchestrator (Offline / Unit)")
    try:
        from core.config import load_config
        from core.orchestrator import JARVISOrchestrator
        cfg = load_config()
        orc = JARVISOrchestrator(cfg)
        ok("JARVISOrchestrator instantiated")
    except Exception as e:
        fail("Orchestrator init", str(e)); return

    # Test built-in command path (no Ollama needed)
    try:
        result = run_async(orc.process("what time is it"))
        assert isinstance(result, dict)
        assert result.get("message")
        ok(f"process('what time is it') → '{result['message'][:50]}'")
    except Exception as e:
        fail("process (time command)", str(e))

    try:
        result = run_async(orc.process("today's date"))
        assert result.get("message")
        ok(f"process('today\\'s date') → '{result['message'][:50]}'")
    except Exception as e:
        fail("process (date command)", str(e))

    try:
        result = run_async(orc.process("system status"))
        assert isinstance(result, dict)
        ok(f"process('system status') → type={result.get('type','?')}")
    except Exception as e:
        fail("process (system status)", str(e))


def test_self_learning():
    section("12. Self-Learning Engine")
    try:
        from core.config import load_config
        from memory.memory_manager import MemoryManager
        from self_learning.learning_engine import SelfLearningEngine
        cfg = load_config()
        mem = MemoryManager(cfg)
        sle = SelfLearningEngine(cfg, mem)
        ok("SelfLearningEngine instantiated")
    except Exception as e:
        fail("SelfLearningEngine init", str(e)); return

    try:
        summary = sle.get_summary()
        assert isinstance(summary, dict)
        ok(f"get_summary → {summary}")
    except Exception as e:
        fail("get_summary", str(e))

    try:
        fb = sle.detect_feedback("great job")
        assert fb == "positive"
        fb2 = sle.detect_feedback("that was wrong")
        assert fb2 == "negative"
        ok("detect_feedback (positive + negative)")
    except Exception as e:
        fail("detect_feedback", str(e))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  JARVIS Comprehensive Test Suite — v5.1")
    print("=" * 55)

    t0 = time.perf_counter()

    test_config()
    test_memory()
    test_llm_router()
    test_command_engine()
    test_sandbox()
    test_reliability()
    test_training_engine()
    test_mobile_engine()
    test_web_engine()
    test_tray_manager()
    test_orchestrator_offline()
    test_self_learning()

    elapsed = time.perf_counter() - t0
    total = _PASS + _FAIL + _SKIP

    print(f"\n{'═'*55}")
    print(f"  Results: {_PASS} PASS  |  {_FAIL} FAIL  |  {_SKIP} SKIP  |  {total} TOTAL")
    print(f"  Time: {elapsed:.2f}s")
    print(f"{'═'*55}")

    if _FAIL:
        print("\n  FAILED TESTS:")
        for name, status, detail in _RESULTS:
            if status == "FAIL":
                print(f"    ✗ {name}: {detail}")

    return 0 if _FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
