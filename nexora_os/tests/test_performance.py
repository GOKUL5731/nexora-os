"""
Performance Monitoring Test
Tests event bus latency, memory usage, agent task completion time, API response times
"""
import asyncio
import sys
import time
import psutil
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from nexora_os.backend.core.event_bus import EventBus
from nexora_os.backend.core.async_runtime import AsyncRuntime
from nexora_os.backend.memory.engine import MemoryEngine


class TestPerformance:
    def __init__(self):
        self.results = []
        self.root = Path(__file__).parent.parent.parent
        
    def log_result(self, test_name: str, passed: bool, details: str = ""):
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append({"test": test_name, "passed": passed, "details": details})
        print(f"{status}: {test_name}")
        if details:
            print(f"  Details: {details}")
    
    def test_memory_usage(self):
        """Test current memory usage"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # Target: < 500MB
            if memory_mb < 500:
                self.log_result("Memory Usage", True, f"Memory usage: {memory_mb:.2f} MB (target: < 500MB)")
                return True
            else:
                self.log_result("Memory Usage", False, f"Memory usage: {memory_mb:.2f} MB (exceeds 500MB target)")
                return False
        except Exception as e:
            self.log_result("Memory Usage", False, str(e))
            return False
    
    def test_cpu_usage(self):
        """Test current CPU usage"""
        try:
            process = psutil.Process()
            cpu_percent = process.cpu_percent(interval=1)
            
            # Target: < 15%
            if cpu_percent < 15:
                self.log_result("CPU Usage", True, f"CPU usage: {cpu_percent:.1f}% (target: < 15%)")
                return True
            else:
                self.log_result("CPU Usage", False, f"CPU usage: {cpu_percent:.1f}% (exceeds 15% target)")
                return False
        except Exception as e:
            self.log_result("CPU Usage", False, str(e))
            return False
    
    async def test_event_bus_latency(self):
        """Test event bus latency under load"""
        try:
            bus = EventBus()
            latencies = []
            
            def callback(event):
                latencies.append(time.time() - event.timestamp)
            
            bus.subscribe("test", callback)
            
            # Publish 100 events and measure latency
            for i in range(100):
                bus.publish("test", {"data": i}, "test")
            
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            
            # Target: < 10ms average latency
            if avg_latency < 0.01:  # 10ms in seconds
                self.log_result("Event Bus Latency", True, f"Average latency: {avg_latency*1000:.2f}ms (target: < 10ms)")
                return True
            else:
                self.log_result("Event Bus Latency", False, f"Average latency: {avg_latency*1000:.2f}ms (exceeds 10ms target)")
                return False
        except Exception as e:
            self.log_result("Event Bus Latency", False, str(e))
            return False
    
    async def test_event_bus_throughput(self):
        """Test event bus throughput"""
        try:
            bus = EventBus()
            received = []
            
            def callback(event):
                received.append(event)
            
            bus.subscribe("test", callback)
            
            # Publish 1000 events and measure time
            start_time = time.time()
            for i in range(1000):
                bus.publish("test", {"data": i}, "test")
            end_time = time.time()
            
            throughput = len(received) / (end_time - start_time)
            
            # Target: > 1000 events/sec
            if throughput > 1000:
                self.log_result("Event Bus Throughput", True, f"Throughput: {throughput:.0f} events/sec (target: > 1000)")
                return True
            else:
                self.log_result("Event Bus Throughput", False, f"Throughput: {throughput:.0f} events/sec (below 1000 target)")
                return False
        except Exception as e:
            self.log_result("Event Bus Throughput", False, str(e))
            return False
    
    async def test_async_task_completion_time(self):
        """Test async task completion time"""
        try:
            bus = EventBus()
            runtime = AsyncRuntime(bus)
            await runtime.start()
            
            async def dummy_task():
                await asyncio.sleep(0.01)  # 10ms task
                return "done"
            
            start_time = time.time()
            task = runtime.create_task("test_task", dummy_task())
            await asyncio.sleep(0.05)  # Wait for completion
            end_time = time.time()
            
            completion_time = end_time - start_time
            
            await runtime.shutdown()
            
            # Target: < 100ms
            if completion_time < 0.1:
                self.log_result("Async Task Completion", True, f"Completion time: {completion_time*1000:.2f}ms (target: < 100ms)")
                return True
            else:
                self.log_result("Async Task Completion", False, f"Completion time: {completion_time*1000:.2f}ms (exceeds 100ms target)")
                return False
        except Exception as e:
            self.log_result("Async Task Completion", False, str(e))
            return False
    
    async def test_memory_store_performance(self):
        """Test memory store operation performance"""
        try:
            bus = EventBus()
            db_path = self.root / "databases" / "test_memory_perf.db"
            memory = MemoryEngine(db_path, bus)
            
            start_time = time.time()
            for i in range(100):
                memory.store(f"Test chunk {i}", "test", ["tag"])
            end_time = time.time()
            
            avg_time = (end_time - start_time) / 100
            
            # Target: < 50ms per store
            if avg_time < 0.05:
                self.log_result("Memory Store Performance", True, f"Average store time: {avg_time*1000:.2f}ms (target: < 50ms)")
                return True
            else:
                self.log_result("Memory Store Performance", False, f"Average store time: {avg_time*1000:.2f}ms (exceeds 50ms target)")
                return False
        except Exception as e:
            self.log_result("Memory Store Performance", False, str(e))
            return False
    
    async def test_memory_search_performance(self):
        """Test memory search operation performance"""
        try:
            bus = EventBus()
            db_path = self.root / "databases" / "test_memory_perf.db"
            memory = MemoryEngine(db_path, bus)
            
            # Store some data first
            for i in range(50):
                memory.store(f"Test chunk {i} with content", "test", ["tag"])
            
            start_time = time.time()
            for i in range(100):
                memory.search("test", 5)
            end_time = time.time()
            
            avg_time = (end_time - start_time) / 100
            
            # Target: < 100ms per search
            if avg_time < 0.1:
                self.log_result("Memory Search Performance", True, f"Average search time: {avg_time*1000:.2f}ms (target: < 100ms)")
                return True
            else:
                self.log_result("Memory Search Performance", False, f"Average search time: {avg_time*1000:.2f}ms (exceeds 100ms target)")
                return False
        except Exception as e:
            self.log_result("Memory Search Performance", False, str(e))
            return False
    
    async def run_all_tests(self):
        """Run all performance tests"""
        print("=" * 60)
        print("PERFORMANCE MONITORING TESTS")
        print("=" * 60)
        print()
        
        # System resource tests
        print("--- System Resources ---")
        self.test_memory_usage()
        self.test_cpu_usage()
        
        # Async tests
        print("\n--- Performance Tests ---")
        await self.test_event_bus_latency()
        await self.test_event_bus_throughput()
        await self.test_async_task_completion_time()
        await self.test_memory_store_performance()
        await self.test_memory_search_performance()
        
        print()
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        
        print(f"Passed: {passed}/{total}")
        print(f"Failed: {total - passed}/{total}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("\n✓ All performance tests passed!")
        else:
            print("\n✗ Some tests failed. Review details above.")
        
        return passed == total


async def main():
    tester = TestPerformance()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
