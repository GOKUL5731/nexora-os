"""
Agent Communication Verification Test
Tests event_bus communication, publish/subscribe, retry, timeout
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from nexora_os.backend.core.event_bus import EventBus
from nexora_os.backend.agents.runtime import AgentRuntime, BaseAgent, PlannerAgent
from nexora_os.backend.memory.engine import MemoryEngine


class AgentCommunicationSuite:
    def __init__(self):
        self.results = []
        self.root = Path(__file__).parent.parent.parent
        
    def log_result(self, test_name: str, passed: bool, details: str = ""):
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append({"test": test_name, "passed": passed, "details": details})
        print(f"{status}: {test_name}")
        if details:
            print(f"  Details: {details}")
    
    def test_event_bus_publish_subscribe(self):
        """Test basic publish/subscribe"""
        try:
            bus = EventBus()
            received = []
            
            def callback(event):
                received.append(event)
            
            bus.subscribe("test.topic", callback)
            bus.publish("test.topic", {"data": "test"}, "test_source")
            
            if len(received) == 1 and received[0].payload == {"data": "test"}:
                self.log_result("Event Bus Publish/Subscribe", True, "Event delivered correctly")
                return True
            else:
                self.log_result("Event Bus Publish/Subscribe", False, f"Expected 1 event, got {len(received)}")
                return False
        except Exception as e:
            self.log_result("Event Bus Publish/Subscribe", False, str(e))
            return False
    
    def test_wildcard_subscription(self):
        """Test wildcard subscription (*)"""
        try:
            bus = EventBus()
            received = []
            
            def callback(event):
                received.append(event.topic)
            
            bus.subscribe("*", callback)
            bus.publish("topic1", {"data": 1}, "source1")
            bus.publish("topic2", {"data": 2}, "source2")
            bus.publish("topic3", {"data": 3}, "source3")
            
            if len(received) == 3:
                self.log_result("Wildcard Subscription", True, f"Received all topics: {received}")
                return True
            else:
                self.log_result("Wildcard Subscription", False, f"Expected 3 events, got {len(received)}")
                return False
        except Exception as e:
            self.log_result("Wildcard Subscription", False, str(e))
            return False
    
    def test_multiple_subscribers(self):
        """Test multiple subscribers to same topic"""
        try:
            bus = EventBus()
            received1 = []
            received2 = []
            
            def callback1(event):
                received1.append(event)
            
            def callback2(event):
                received2.append(event)
            
            bus.subscribe("test.topic", callback1)
            bus.subscribe("test.topic", callback2)
            bus.publish("test.topic", {"data": "test"}, "source")
            
            if len(received1) == 1 and len(received2) == 1:
                self.log_result("Multiple Subscribers", True, "Both subscribers received event")
                return True
            else:
                self.log_result("Multiple Subscribers", False, f"Subscriber1: {len(received1)}, Subscriber2: {len(received2)}")
                return False
        except Exception as e:
            self.log_result("Multiple Subscribers", False, str(e))
            return False
    
    def test_unsubscribe(self):
        """Test unsubscribe functionality"""
        try:
            bus = EventBus()
            received = []
            
            def callback(event):
                received.append(event)
            
            unsubscribe = bus.subscribe("test.topic", callback)
            bus.publish("test.topic", {"data": "before"}, "source")
            unsubscribe()
            bus.publish("test.topic", {"data": "after"}, "source")
            
            if len(received) == 1 and received[0].payload == {"data": "before"}:
                self.log_result("Unsubscribe", True, "Unsubscribe prevented further events")
                return True
            else:
                self.log_result("Unsubscribe", False, f"Expected 1 event, got {len(received)}")
                return False
        except Exception as e:
            self.log_result("Unsubscribe", False, str(e))
            return False
    
    def test_event_history(self):
        """Test event history tracking"""
        try:
            bus = EventBus()
            
            for i in range(10):
                bus.publish(f"topic{i}", {"data": i}, "source")
            
            history = bus.history(limit=5)
            
            if len(history) == 5:
                self.log_result("Event History", True, f"Retrieved {len(history)} events from history")
                return True
            else:
                self.log_result("Event History", False, f"Expected 5 events, got {len(history)}")
                return False
        except Exception as e:
            self.log_result("Event History", False, str(e))
            return False
    
    def test_event_metrics(self):
        """Test event metrics collection"""
        try:
            bus = EventBus()
            
            for i in range(20):
                bus.publish("test", {"data": i}, "source")
            
            metrics = bus.metrics()
            
            if metrics.get("published_count") >= 20 and metrics.get("events_per_sec") > 0:
                self.log_result("Event Metrics", True, f"Metrics: {metrics}")
                return True
            else:
                self.log_result("Event Metrics", False, f"Incomplete metrics: {metrics}")
                return False
        except Exception as e:
            self.log_result("Event Metrics", False, str(e))
            return False
    
    def test_state_management(self):
        """Test state set/get/snapshot"""
        try:
            bus = EventBus()
            
            bus.set_state("key1", "value1", "source1")
            bus.set_state("key2", "value2", "source2")
            
            value1 = bus.get_state("key1")
            value2 = bus.get_state("key2")
            snapshot = bus.state_snapshot()
            
            if value1 == "value1" and value2 == "value2" and len(snapshot) == 2:
                self.log_result("State Management", True, f"State managed correctly: {snapshot}")
                return True
            else:
                self.log_result("State Management", False, f"State not managed correctly")
                return False
        except Exception as e:
            self.log_result("State Management", False, str(e))
            return False
    
    async def test_agent_event_publishing(self):
        """Test agents publish events correctly"""
        try:
            bus = EventBus()
            db_path = self.root / "databases" / "test_memory.db"
            memory = MemoryEngine(db_path, bus)
            
            received_events = []
            
            def capture_events(event):
                received_events.append(event.topic)
            
            bus.subscribe("*", capture_events)
            
            # Create a simple agent
            agent = PlannerAgent("TestAgent", bus, memory)
            agent.start()
            
            # Submit a task to trigger agent events
            await agent.submit({"goal": "test goal"})
            
            # Wait for events to be processed
            await asyncio.sleep(0.5)
            
            await agent.stop()
            
            # Check if agent published expected events
            expected_events = ["agent.queued", "agent.started", "agent.completed"]
            found_events = [e for e in expected_events if e in received_events]
            
            if len(found_events) >= 2:  # At least queued and started
                self.log_result("Agent Event Publishing", True, f"Agent published events: {found_events}")
                return True
            else:
                self.log_result("Agent Event Publishing", False, f"Agent events not published correctly: {received_events}")
                return False
        except Exception as e:
            self.log_result("Agent Event Publishing", False, str(e))
            return False
    
    async def test_agent_error_handling(self):
        """Test agent error handling and error events"""
        try:
            bus = EventBus()
            db_path = self.root / "databases" / "test_memory.db"
            memory = MemoryEngine(db_path, bus)
            
            error_events = []
            
            def capture_errors(event):
                if "error" in event.topic or "failed" in event.topic:
                    error_events.append(event.topic)
            
            bus.subscribe("*", capture_errors)
            
            # Create an agent that will fail
            class FailingAgent(BaseAgent):
                async def execute(self, task, context):
                    raise Exception("Test error")
            
            agent = FailingAgent("FailingAgent", bus, memory)
            agent.start()
            
            await agent.submit({"goal": "test"})
            
            await asyncio.sleep(0.5)
            await agent.stop()
            
            if "agent.failed" in error_events:
                self.log_result("Agent Error Handling", True, f"Error events published: {error_events}")
                return True
            else:
                self.log_result("Agent Error Handling", False, f"Error events not published: {error_events}")
                return False
        except Exception as e:
            self.log_result("Agent Error Handling", False, str(e))
            return False
    
    async def test_event_bus_error_counting(self):
        """Test event bus counts subscriber errors"""
        try:
            bus = EventBus()
            
            def failing_callback(event):
                raise Exception("Test error")
            
            bus.subscribe("test", failing_callback)
            
            # Publish events that will cause errors
            for i in range(5):
                bus.publish("test", {"data": i}, "source")
            
            metrics = bus.metrics()
            
            if metrics.get("subscriber_error_count") >= 5:
                self.log_result("Event Bus Error Counting", True, f"Error count: {metrics.get('subscriber_error_count')}")
                return True
            else:
                self.log_result("Event Bus Error Counting", False, f"Error count not tracked: {metrics}")
                return False
        except Exception as e:
            self.log_result("Event Bus Error Counting", False, str(e))
            return False
    
    async def run_all_tests(self):
        """Run all agent communication tests"""
        print("=" * 60)
        print("AGENT COMMUNICATION VERIFICATION TESTS")
        print("=" * 60)
        print()
        
        # Synchronous tests
        print("--- Event Bus Tests ---")
        self.test_event_bus_publish_subscribe()
        self.test_wildcard_subscription()
        self.test_multiple_subscribers()
        self.test_unsubscribe()
        self.test_event_history()
        self.test_event_metrics()
        self.test_state_management()
        
        # Async tests
        print("\n--- Agent Communication Tests ---")
        await self.test_agent_event_publishing()
        await self.test_agent_error_handling()
        await self.test_event_bus_error_counting()
        
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
            print("\n✓ All agent communication tests passed!")
        else:
            print("\n✗ Some tests failed. Review details above.")
        
        return passed == total


async def main():
    tester = AgentCommunicationSuite()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
