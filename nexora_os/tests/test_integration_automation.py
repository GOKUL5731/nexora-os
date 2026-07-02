"""
Automation Engine Integration Test
Tests app launch, file operations, browser automation
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from nexora_os.backend.core.event_bus import EventBus
from nexora_os.backend.vision.engine import VisionEngine
from nexora_os.backend.automation.engine import AutomationEngine


class TestAutomationIntegration:
    def __init__(self):
        self.results = []
        self.root = Path(__file__).parent.parent.parent
        
    def log_result(self, test_name: str, passed: bool, details: str = ""):
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append({"test": test_name, "passed": passed, "details": details})
        print(f"{status}: {test_name}")
        if details:
            print(f"  Details: {details}")
    
    def test_automation_engine_initialization(self):
        """Test automation engine can be initialized"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            vision = VisionEngine(captures_path, bus)
            engine = AutomationEngine(bus, vision)
            self.log_result("Automation Engine Initialization", True, "AutomationEngine initialized successfully")
            return True
        except Exception as e:
            self.log_result("Automation Engine Initialization", False, str(e))
            return False
    
    def test_automation_engine_status(self):
        """Test automation engine status"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            vision = VisionEngine(captures_path, bus)
            engine = AutomationEngine(bus, vision)
            status = engine.status()
            if status and isinstance(status, dict):
                self.log_result("Automation Engine Status", True, f"Status returned: {status}")
                return True
            else:
                self.log_result("Automation Engine Status", False, f"Invalid status: {status}")
                return False
        except Exception as e:
            self.log_result("Automation Engine Status", False, str(e))
            return False
    
    async def test_automation_list_actions(self):
        """Test listing registered automation actions"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            vision = VisionEngine(captures_path, bus)
            engine = AutomationEngine(bus, vision)
            
            actions = engine.list()
            if isinstance(actions, list) and len(actions) > 0:
                self.log_result("List Actions", True, f"Found {len(actions)} registered actions")
                return True
            else:
                self.log_result("List Actions", False, f"No actions found: {actions}")
                return False
        except Exception as e:
            self.log_result("List Actions", False, str(e))
            return False
    
    async def test_system_status_action(self):
        """Test system status automation action"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            vision = VisionEngine(captures_path, bus)
            engine = AutomationEngine(bus, vision)
            
            result = await engine.execute("system status")
            if result.get("ok"):
                self.log_result("System Status Action", True, f"System status retrieved")
                return True
            else:
                self.log_result("System Status Action", False, f"Failed: {result.get('error', 'Unknown')}")
                return False
        except Exception as e:
            self.log_result("System Status Action", False, str(e))
            return False
    
    async def test_time_action(self):
        """Test time automation action"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            vision = VisionEngine(captures_path, bus)
            engine = AutomationEngine(bus, vision)
            
            result = await engine.execute("time")
            if result.get("ok"):
                self.log_result("Time Action", True, f"Time retrieved: {result.get('message', '')}")
                return True
            else:
                self.log_result("Time Action", False, f"Failed: {result.get('error', 'Unknown')}")
                return False
        except Exception as e:
            self.log_result("Time Action", False, str(e))
            return False
    
    async def test_screenshot_action(self):
        """Test screenshot automation action"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            vision = VisionEngine(captures_path, bus)
            engine = AutomationEngine(bus, vision)
            
            result = await engine.execute("screenshot")
            if result.get("ok"):
                self.log_result("Screenshot Action", True, f"Screenshot taken: {result.get('path', '')}")
                return True
            else:
                self.log_result("Screenshot Action", False, f"Failed: {result.get('error', 'Unknown')}")
                return False
        except Exception as e:
            self.log_result("Screenshot Action", False, str(e))
            return False
    
    async def test_file_create_action(self):
        """Test file creation automation action"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            vision = VisionEngine(captures_path, bus)
            engine = AutomationEngine(bus, vision)
            
            test_file = self.root / "logs" / "test_automation.txt"
            result = await engine.execute(f"create file {test_file} with content test")
            
            # Clean up
            if test_file.exists():
                test_file.unlink()
            
            if result.get("ok"):
                self.log_result("File Create Action", True, f"File created successfully")
                return True
            else:
                self.log_result("File Create Action", False, f"Failed: {result.get('error', 'Unknown')}")
                return False
        except Exception as e:
            self.log_result("File Create Action", False, str(e))
            return False
    
    async def test_browser_open_action(self):
        """Test browser open automation action"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            vision = VisionEngine(captures_path, bus)
            engine = AutomationEngine(bus, vision)
            
            # Test with a safe URL
            result = await engine.execute("open browser https://example.com")
            if result.get("ok"):
                self.log_result("Browser Open Action", True, f"Browser opened")
                return True
            else:
                self.log_result("Browser Open Action", False, f"Failed: {result.get('error', 'Unknown')}")
                return False
        except Exception as e:
            self.log_result("Browser Open Action", False, str(e))
            return False
    
    async def run_all_tests(self):
        """Run all automation integration tests"""
        print("=" * 60)
        print("AUTOMATION ENGINE INTEGRATION TESTS")
        print("=" * 60)
        print()
        
        # Synchronous tests
        print("--- Automation Engine Tests ---")
        self.test_automation_engine_initialization()
        self.test_automation_engine_status()
        
        # Async tests
        print("\n--- Automation Pipeline Tests ---")
        await self.test_automation_list_actions()
        await self.test_system_status_action()
        await self.test_time_action()
        await self.test_screenshot_action()
        await self.test_file_create_action()
        await self.test_browser_open_action()
        
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
            print("\n✓ All automation integration tests passed!")
        else:
            print("\n✗ Some tests failed. Review details above.")
        
        return passed == total


async def main():
    tester = TestAutomationIntegration()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
