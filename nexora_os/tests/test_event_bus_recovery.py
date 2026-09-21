import asyncio

from nexora_os.backend.core.event_bus import EventBus


def test_preloop_publication_does_not_disable_async_delivery():
    bus = EventBus(enable_async_delivery=True)
    bus.publish("startup", {})

    async def run():
        delivered = asyncio.Event()
        bus.subscribe("ready", lambda event: delivered.set())
        bus.publish("ready", {})
        await asyncio.wait_for(delivered.wait(), 1)
        assert bus.metrics()["async_delivery_enabled"] is True
        assert bus._delivery_task is not None
        await bus.shutdown()

    asyncio.run(run())


def test_queue_overflow_is_accounted_without_loop_errors():
    async def run():
        bus = EventBus(enable_async_delivery=True, queue_size=1)
        loop = asyncio.get_running_loop()
        errors = []
        previous = loop.get_exception_handler()
        loop.set_exception_handler(lambda loop, context: errors.append(context))
        try:
            for index in range(50):
                bus.publish("burst", index)
            await asyncio.sleep(0.05)
            assert errors == []
            assert bus.metrics()["dropped_count"] > 0
        finally:
            await bus.shutdown()
            loop.set_exception_handler(previous)

    asyncio.run(run())


def test_delivery_restarts_after_shutdown():
    async def run():
        bus = EventBus(enable_async_delivery=True)
        delivered = asyncio.Event()
        bus.subscribe("probe", lambda event: delivered.set())
        for _ in range(2):
            delivered.clear()
            bus.publish("probe", {})
            await asyncio.wait_for(delivered.wait(), 1)
            await bus.shutdown()

    asyncio.run(run())
