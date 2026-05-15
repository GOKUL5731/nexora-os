"""
FIX MODE runtime infrastructure tests.

Run:
  python -X utf8 tests/test_runtime_infrastructure.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def assert_true(value, message: str):
    if not value:
        raise AssertionError(message)


async def test_event_bus_delivery_and_tracing():
    from core.event_bus import EventBus

    bus = EventBus(history_limit=1000)
    received = []
    async_received = []

    def sync_sub(event):
        received.append(event)

    async def async_sub(event):
        await asyncio.sleep(0)
        async_received.append(event)

    bus.subscribe("voice.input", sync_sub)
    bus.subscribe("voice.*", async_sub)
    event = await bus.publish_async("voice.input", {"text": "hello"}, source="test")

    assert_true(event.sequence == 1, "event sequence should start at 1")
    assert_true(len(received) == 1, "sync subscriber should receive event")
    assert_true(len(async_received) == 1, "async wildcard subscriber should receive event")
    assert_true(bus.stats()["published_count"] == 1, "published count should be tracked")
    assert_true(bus.history(limit=1)[0].topic == "voice.input", "history should include event")


def test_event_bus_thread_safety():
    from core.event_bus import EventBus

    bus = EventBus(history_limit=5000)
    count = 0
    lock = threading.Lock()

    def sub(_event):
        nonlocal count
        with lock:
            count += 1

    bus.subscribe("stress.*", sub)

    def worker(index):
        for item in range(100):
            bus.publish(f"stress.{index}", {"item": item}, source="thread")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert_true(count == 800, f"expected 800 deliveries, got {count}")
    assert_true(bus.stats()["subscriber_error_count"] == 0, "subscriber errors should stay zero")


async def test_event_bus_async_subscriber_from_sync_publish():
    from core.async_runtime import get_async_runtime
    from core.event_bus import EventBus

    bus = EventBus()
    received = []

    async def async_sub(event):
        received.append(event.payload["value"])

    bus.subscribe("sync.publish", async_sub)
    bus.publish("sync.publish", {"value": 7}, source="test")
    deadline = time.time() + 3
    while not received and time.time() < deadline:
        await asyncio.sleep(0.02)
    get_async_runtime().stop()
    assert_true(received == [7], "async subscriber should run from sync publish via runtime")


async def test_module_manager_lifecycle_and_recovery():
    from core.event_bus import EventBus
    from core.module_manager import ModuleManager

    bus = EventBus()
    manager = ModuleManager(bus=bus)
    state = {"started": 0, "stopped": 0}

    class TestModule:
        def start(self):
            state["started"] += 1

        def stop(self):
            state["stopped"] += 1

        def restart(self):
            state["stopped"] += 1
            state["started"] += 1

        def health_check(self):
            return {"status": "running", "latency_ms": 1.2}

        def status(self):
            return "disabled"

    manager.register("dependency", status="running")
    manager.register("test_module", module=TestModule(), dependencies=["dependency"])

    started = await manager.start_module("test_module")
    assert_true(started["ok"], "module should start")
    restarted = await manager.restart_module("test_module")
    assert_true(restarted["ok"], "module should restart")
    health = manager.run_health_checks()["test_module"]
    assert_true(health["status"] == "running", "health check should update status")
    stopped = await manager.stop_module("test_module")
    assert_true(stopped["ok"], "module should stop")
    assert_true(state["started"] >= 2 and state["stopped"] >= 2, "lifecycle hooks should run")

    manager.register("bad_module", dependencies=["missing"])
    failed = await manager.start_module("bad_module")
    assert_true(not failed["ok"], "missing dependency should fail startup")
    assert_true(manager.failed_modules(), "failed module should be tracked")


def test_async_runtime_scheduling_and_shutdown():
    from core.async_runtime import AsyncRuntime
    from core.event_bus import EventBus

    runtime = AsyncRuntime(bus=EventBus(), max_workers=2)

    async def coro():
        await asyncio.sleep(0.01)
        return 42

    future = runtime.submit(coro(), name="unit-coro")
    assert_true(future.result(timeout=5) == 42, "coroutine result should return")
    blocking = runtime.run_blocking(lambda: "ok", name="unit-blocking")
    assert_true(blocking.result(timeout=5) == "ok", "blocking result should return")
    health = runtime.health_check()
    assert_true(health["thread_alive"], "runtime thread should be alive")
    assert_true(health["tasks_total"] >= 2, "runtime should track tasks")
    runtime.stop()
    assert_true(not runtime.health_check()["thread_alive"], "runtime should stop cleanly")


def test_logger_and_health_monitor():
    from core.event_bus import EventBus
    from core.health_monitor import HealthMonitor
    from core.logger import log_timing, setup_runtime_logging
    from core.module_manager import ModuleManager

    log_file = ROOT / "logs" / "runtime_infrastructure_test.log"
    logger = setup_runtime_logging("jarvis.runtime_test", log_file=log_file)
    with log_timing(logger, "runtime-test-operation"):
        time.sleep(0.001)
    logger.warning("runtime test warning")
    logging.getLogger().handlers[0].flush() if logging.getLogger().handlers else None

    bus = EventBus()
    modules = ModuleManager(bus=bus)
    modules.register("event_bus", status="running")
    modules.register("async_runtime", status="running", health_check=lambda: {"status": "running", "thread_alive": True})
    health = HealthMonitor(bus=bus, modules=modules)
    snapshot = health.snapshot()
    report = health.report()

    assert_true("event_bus" in snapshot, "health should include event bus stats")
    assert_true("threads" in snapshot, "health should include thread status")
    assert_true(report["summary"]["active_modules"] >= 2, "health report should count modules")
    time.sleep(0.05)
    assert_true((ROOT / "logs" / "jarvis.log").exists() or log_file.exists(), "rotating log file should be created")


async def main():
    tests = [
        test_event_bus_delivery_and_tracing,
        test_event_bus_thread_safety,
        test_event_bus_async_subscriber_from_sync_publish,
        test_module_manager_lifecycle_and_recovery,
        test_async_runtime_scheduling_and_shutdown,
        test_logger_and_health_monitor,
    ]
    passed = 0
    for test in tests:
        try:
            if asyncio.iscoroutinefunction(test):
                await test()
            else:
                test()
            passed += 1
            print(f"PASS {test.__name__}", flush=True)
        except Exception as exc:
            print(f"FAIL {test.__name__}: {exc}", flush=True)
            raise
    print(f"\nRuntime infrastructure tests: {passed}/{len(tests)} passed", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
