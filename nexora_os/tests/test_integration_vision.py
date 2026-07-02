"""
Vision Pipeline Integration Test
Tests camera → frame processing → OCR → object detection
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from nexora_os.backend.core.event_bus import EventBus
from nexora_os.backend.vision.engine import VisionEngine


class TestVisionIntegration:
    def __init__(self):
        self.results = []
        self.root = Path(__file__).parent.parent.parent
        
    def log_result(self, test_name: str, passed: bool, details: str = ""):
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append({"test": test_name, "passed": passed, "details": details})
        print(f"{status}: {test_name}")
        if details:
            print(f"  Details: {details}")
    
    def test_vision_engine_initialization(self):
        """Test vision engine can be initialized"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            engine = VisionEngine(captures_path, bus)
            self.log_result("Vision Engine Initialization", True, "VisionEngine initialized successfully")
            return True
        except Exception as e:
            self.log_result("Vision Engine Initialization", False, str(e))
            return False
    
    def test_vision_engine_health(self):
        """Test vision engine health check"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            engine = VisionEngine(captures_path, bus)
            health = engine.health()
            if health and isinstance(health, dict):
                self.log_result("Vision Engine Health", True, f"Health check returned: {health}")
                return True
            else:
                self.log_result("Vision Engine Health", False, f"Health check returned invalid: {health}")
                return False
        except Exception as e:
            self.log_result("Vision Engine Health", False, str(e))
            return False
    
    async def test_camera_start_stop(self):
        """Test camera start and stop functionality"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            engine = VisionEngine(captures_path, bus)
            
            # Start camera
            start_result = await engine.start()
            if not start_result.get("ok"):
                self.log_result("Camera Start/Stop", False, f"Camera start failed: {start_result.get('error', 'Unknown')}")
                return False
            
            # Stop camera
            stop_result = await engine.stop()
            if not stop_result.get("ok"):
                self.log_result("Camera Start/Stop", False, f"Camera stop failed: {stop_result.get('error', 'Unknown')}")
                return False
            
            self.log_result("Camera Start/Stop", True, "Camera started and stopped successfully")
            return True
        except Exception as e:
            self.log_result("Camera Start/Stop", False, str(e))
            return False
    
    async def test_screen_capture(self):
        """Test screen capture functionality"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            engine = VisionEngine(captures_path, bus)
            
            result = await engine.screen(ocr=False)
            if result.get("ok"):
                self.log_result("Screen Capture", True, f"Screen captured: {result.get('path', '')}")
                return True
            else:
                self.log_result("Screen Capture", False, f"Screen capture failed: {result.get('error', 'Unknown')}")
                return False
        except Exception as e:
            self.log_result("Screen Capture", False, str(e))
            return False
    
    async def test_screen_ocr(self):
        """Test screen capture with OCR"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            engine = VisionEngine(captures_path, bus)
            
            result = await engine.screen(ocr=True)
            if result.get("ok"):
                ocr_text = result.get("ocr_text", "")
                self.log_result("Screen OCR", True, f"OCR completed, text length: {len(ocr_text)}")
                return True
            else:
                self.log_result("Screen OCR", False, f"OCR failed: {result.get('error', 'Unknown')}")
                return False
        except Exception as e:
            self.log_result("Screen OCR", False, str(e))
            return False
    
    async def test_mouse_control_toggle(self):
        """Test mouse control enable/disable"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            engine = VisionEngine(captures_path, bus)
            
            # Enable mouse control
            enable_result = await engine.enable_mouse_control()
            if not enable_result.get("ok"):
                self.log_result("Mouse Control Toggle", False, f"Enable failed: {enable_result.get('error', 'Unknown')}")
                return False
            
            # Check state
            state = await engine.get_mouse_state()
            if not state.get("enabled"):
                self.log_result("Mouse Control Toggle", False, "Mouse control not enabled")
                return False
            
            # Disable mouse control
            disable_result = await engine.disable_mouse_control()
            if not disable_result.get("ok"):
                self.log_result("Mouse Control Toggle", False, f"Disable failed: {disable_result.get('error', 'Unknown')}")
                return False
            
            self.log_result("Mouse Control Toggle", True, "Mouse control enabled and disabled successfully")
            return True
        except Exception as e:
            self.log_result("Mouse Control Toggle", False, str(e))
            return False
    
    async def test_gesture_control_toggle(self):
        """Test gesture control enable/disable"""
        try:
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            engine = VisionEngine(captures_path, bus)
            
            # Enable gesture control
            enable_result = await engine.enable_gesture_control()
            if not enable_result.get("ok"):
                self.log_result("Gesture Control Toggle", False, f"Enable failed: {enable_result.get('error', 'Unknown')}")
                return False
            
            # Check state
            state = await engine.get_gesture_state()
            if not state.get("enabled"):
                self.log_result("Gesture Control Toggle", False, "Gesture control not enabled")
                return False
            
            # Disable gesture control
            disable_result = await engine.disable_gesture_control()
            if not disable_result.get("ok"):
                self.log_result("Gesture Control Toggle", False, f"Disable failed: {disable_result.get('error', 'Unknown')}")
                return False
            
            self.log_result("Gesture Control Toggle", True, "Gesture control enabled and disabled successfully")
            return True
        except Exception as e:
            self.log_result("Gesture Control Toggle", False, str(e))
            return False
    
    async def run_all_tests(self):
        """Run all vision integration tests"""
        print("=" * 60)
        print("VISION PIPELINE INTEGRATION TESTS")
        print("=" * 60)
        print()
        
        # Synchronous tests
        print("--- Vision Engine Tests ---")
        self.test_vision_engine_initialization()
        self.test_vision_engine_health()
        
        # Async tests
        print("\n--- Vision Pipeline Tests ---")
        await self.test_camera_start_stop()
        await self.test_screen_capture()
        await self.test_screen_ocr()
        await self.test_mouse_control_toggle()
        await self.test_gesture_control_toggle()
        
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
            print("\n✓ All vision integration tests passed!")
        else:
            print("\n✗ Some tests failed. Review details above.")
        
        return passed == total


async def main():
    tester = TestVisionIntegration()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
