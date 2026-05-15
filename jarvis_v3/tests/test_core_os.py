"""
JARVIS CORE OS test suite.

Run:
  python -X utf8 tests/test_core_os.py
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import load_config


def assert_true(value, message: str):
    if not value:
        raise AssertionError(message)


async def test_command_engine_direct_time():
    from core.command_engine import CommandEngine

    decision = await CommandEngine(load_config()).try_execute("what time is it")
    assert_true(decision.handled, "time command should be handled directly")
    assert_true("It is" in decision.message, "time response should be deterministic")
    assert_true(decision.confidence > 0.9, "time confidence should be high")


def test_memory_cognitive_tables():
    from memory.memory_manager import MemoryManager

    cfg = load_config()
    cfg["memory"]["db_path"] = "database/test_core_os_memory.db"
    memory = MemoryManager(cfg)
    event_id = memory.store_event("test", "core os event", {"ok": True}, importance=0.8)
    memory.learn_preference("theme", "dark mode", source="test", confidence=0.9)
    memory.remember_error("sample error", "sample fix", {"module": "test"}, resolved=True)
    vector_id = memory.store_vector_memory("open visual studio code quickly", {"tool": "open_app"})

    assert_true(event_id, "event id should be returned")
    assert_true(vector_id, "vector id should be returned")
    assert_true(memory.recent_events(1)[0]["summary"] == "core os event", "event should be retrievable")
    assert_true(memory.get_preferences()["theme"]["value"] == "dark mode", "preference should be retrievable")
    assert_true(memory.find_solution("sample error")["resolved"], "error solution should be retrievable")
    matches = memory.search_vector_memory("open code quickly", limit=3)
    assert_true(matches, "vector memory should return a local match")


def test_sandbox_engine_runs_python():
    from core.sandbox_engine import SandboxEngine

    sandbox = SandboxEngine(load_config())
    session = sandbox.create_session("test")
    try:
        sandbox.write_file(session, "hello.py", "print('sandbox-ok')\n")
        result = sandbox.run_python(session, "hello.py")
        assert_true(result.ok, result.stderr)
        assert_true("sandbox-ok" in result.stdout, "sandbox stdout should be captured")
    finally:
        sandbox.cleanup_session(session)


async def test_reliability_retry():
    from core.reliability_engine import ReliabilityEngine

    reliability = ReliabilityEngine({"reliability": {"max_retries": 2, "retry_backoff_ms": 1}})
    state = {"calls": 0}

    async def operation():
        state["calls"] += 1
        if state["calls"] < 2:
            raise RuntimeError("transient")
        return {"ok": True, "value": 42}

    result = await reliability.execute_with_retry("transient-test", operation)
    assert_true(result["ok"], "retry should recover")
    assert_true(result["attempts"] == 2, "retry should stop after success")


def test_evolution_analysis_and_plugin_sandbox():
    from core.upgrade_engine import EvolutionEngine

    engine = EvolutionEngine(load_config())
    report = engine.analyze_codebase(["core"])
    assert_true(report["module_count"] > 0, "analysis should inspect core modules")
    assert_true(report["recommendations"], "analysis should include recommendations")

    plugin_code = """
def register(config: dict) -> dict:
    def sandbox_ping(args: dict) -> dict:
        return {"pong": args.get("value", "ok")}

    return {
        "name": "Sandbox Test",
        "version": "1.0.0",
        "description": "Test plugin for sandbox validation.",
        "author": "tests",
        "tools": {"sandbox_ping": sandbox_ping},
    }
"""
    result = engine.sandbox_plugin(plugin_code, "sandbox_test")
    assert_true(result["ok"], f"plugin should pass sandbox validation: {result}")


def test_compatibility_imports():
    from core.benchmark_engine import BenchmarkEngine
    from core.coder_engine import CoderEngine
    from core.learning_engine import ContinuousLearningEngine
    from core.memory_engine import MemoryEngine
    from core.safety_engine import SafetyEngine
    from core.tts_engine import TTSEngine
    from core.vision_engine import VisionEngine
    from core.voice_engine import VoiceEngine

    for obj in [BenchmarkEngine, CoderEngine, ContinuousLearningEngine, MemoryEngine, SafetyEngine, TTSEngine, VisionEngine, VoiceEngine]:
        assert_true(obj is not None, "compatibility import should resolve")


async def test_core_os_health():
    from core.jarvis_core_os import JarvisCoreOS

    core = JarvisCoreOS(load_config())
    health = core.health()
    assert_true(health["status"] == "online", "core os should report online")
    assert_true(health["tools"] > 0, "core os should expose tools")
    response = await core.process("what time is it")
    assert_true(response["type"] == "success", "core direct command should succeed")


async def main():
    tests = [
        test_command_engine_direct_time,
        test_memory_cognitive_tables,
        test_sandbox_engine_runs_python,
        test_reliability_retry,
        test_evolution_analysis_and_plugin_sandbox,
        test_compatibility_imports,
        test_core_os_health,
    ]
    passed = 0
    for test in tests:
        try:
            if inspect.iscoroutinefunction(test):
                await test()
            else:
                test()
            passed += 1
            print(f"PASS {test.__name__}")
        except Exception as exc:
            print(f"FAIL {test.__name__}: {exc}")
            raise
    print(f"\nCORE OS tests: {passed}/{len(tests)} passed")


if __name__ == "__main__":
    asyncio.run(main())
