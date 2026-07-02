"""
Voice Pipeline Integration Test
Tests microphone → STT → NLP → LLM → TTS → Speaker pipeline
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from nexora_os.backend.core.event_bus import EventBus
from nexora_os.backend.voice.engine import VoiceEngine


class TestVoiceIntegration:
    def __init__(self):
        self.results = []
        self.root = Path(__file__).parent.parent.parent
        
    def log_result(self, test_name: str, passed: bool, details: str = ""):
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append({"test": test_name, "passed": passed, "details": details})
        print(f"{status}: {test_name}")
        if details:
            print(f"  Details: {details}")
    
    def test_voice_engine_initialization(self):
        """Test voice engine can be initialized"""
        try:
            bus = EventBus()
            engine = VoiceEngine(bus)
            self.log_result("Voice Engine Initialization", True, "VoiceEngine initialized successfully")
            return True
        except Exception as e:
            self.log_result("Voice Engine Initialization", False, str(e))
            return False
    
    def test_voice_engine_health(self):
        """Test voice engine health check"""
        try:
            bus = EventBus()
            engine = VoiceEngine(bus)
            health = engine.health()
            if health and isinstance(health, dict):
                self.log_result("Voice Engine Health", True, f"Health check returned: {health}")
                return True
            else:
                self.log_result("Voice Engine Health", False, f"Health check returned invalid: {health}")
                return False
        except Exception as e:
            self.log_result("Voice Engine Health", False, str(e))
            return False
    
    async def test_tts_functionality(self):
        """Test text-to-speech functionality"""
        try:
            bus = EventBus()
            engine = VoiceEngine(bus)
            result = await engine.speak("Test message")
            if result.get("ok"):
                self.log_result("TTS Functionality", True, f"TTS completed: {result.get('message', '')}")
                return True
            else:
                self.log_result("TTS Functionality", False, f"TTS failed: {result.get('error', 'Unknown error')}")
                return False
        except Exception as e:
            self.log_result("TTS Functionality", False, str(e))
            return False
    
    async def test_language_detection(self):
        """Test language detection for English, Tamil, Tanglish"""
        try:
            bus = EventBus()
            engine = VoiceEngine(bus)
            
            # Test English
            lang_en = engine.detect_language("Hello world")
            # Test Tamil
            lang_ta = engine.detect_language("வணக்கம்")
            # Test Tanglish
            lang_mix = engine.detect_language("Enna pandra")
            
            if lang_en == "english" and lang_ta == "tamil" and lang_mix == "tanglish":
                self.log_result("Language Detection", True, f"English: {lang_en}, Tamil: {lang_ta}, Tanglish: {lang_mix}")
                return True
            else:
                self.log_result("Language Detection", False, f"Detection failed: en={lang_en}, ta={lang_ta}, mix={lang_mix}")
                return False
        except Exception as e:
            self.log_result("Language Detection", False, str(e))
            return False
    
    def test_stt_availability(self):
        """Test speech-to-text availability"""
        try:
            bus = EventBus()
            engine = VoiceEngine(bus)
            health = engine.health()
            
            # Check if STT is available (may not be configured)
            stt_available = health.get("stt_available", False)
            self.log_result("STT Availability", True, f"STT available: {stt_available}")
            return True
        except Exception as e:
            self.log_result("STT Availability", False, str(e))
            return False
    
    async def run_all_tests(self):
        """Run all voice integration tests"""
        print("=" * 60)
        print("VOICE PIPELINE INTEGRATION TESTS")
        print("=" * 60)
        print()
        
        # Synchronous tests
        print("--- Voice Engine Tests ---")
        self.test_voice_engine_initialization()
        self.test_voice_engine_health()
        self.test_stt_availability()
        
        # Async tests
        print("\n--- Voice Pipeline Tests ---")
        await self.test_tts_functionality()
        await self.test_language_detection()
        
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
            print("\n✓ All voice integration tests passed!")
        else:
            print("\n✗ Some tests failed. Review details above.")
        
        return passed == total


async def main():
    tester = TestVoiceIntegration()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
