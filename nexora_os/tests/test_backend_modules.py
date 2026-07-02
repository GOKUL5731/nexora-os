"""
Backend Modules Verification Test
Tests imports, initialization, execution, cleanup, and error handling for all backend modules
"""
import os
import sys
from pathlib import Path

# Change to backend directory and add it to path
backend_dir = Path(__file__).parent.parent / "backend"
os.chdir(str(backend_dir))
sys.path.insert(0, str(backend_dir))

from core.event_bus import EventBus


class TestBackendModules:
    def __init__(self):
        self.results = []
        self.root = Path(__file__).parent.parent.parent
        
    def log_result(self, test_name: str, passed: bool, details: str = ""):
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append({"test": test_name, "passed": passed, "details": details})
        print(f"{status}: {test_name}")
        if details:
            print(f"  Details: {details}")
    
    def test_voice_engine_import(self):
        """Test voice engine can be imported"""
        try:
            from voice.engine import VoiceEngine
            self.log_result("Voice Engine Import", True, "VoiceEngine imported successfully")
            return True
        except Exception as e:
            self.log_result("Voice Engine Import", False, str(e))
            return False
    
    def test_voice_engine_initialization(self):
        """Test voice engine can be initialized"""
        try:
            from voice.engine import VoiceEngine
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
            from voice.engine import VoiceEngine
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
    
    def test_vision_engine_import(self):
        """Test vision engine can be imported"""
        try:
            from vision.engine import VisionEngine
            self.log_result("Vision Engine Import", True, "VisionEngine imported successfully")
            return True
        except Exception as e:
            self.log_result("Vision Engine Import", False, str(e))
            return False
    
    def test_vision_engine_initialization(self):
        """Test vision engine can be initialized"""
        try:
            from vision.engine import VisionEngine
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
            from vision.engine import VisionEngine
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
    
    def test_memory_engine_import(self):
        """Test memory engine can be imported"""
        try:
            from memory.engine import MemoryEngine
            self.log_result("Memory Engine Import", True, "MemoryEngine imported successfully")
            return True
        except Exception as e:
            self.log_result("Memory Engine Import", False, str(e))
            return False
    
    def test_memory_engine_initialization(self):
        """Test memory engine can be initialized"""
        try:
            from memory.engine import MemoryEngine
            bus = EventBus()
            db_path = self.root / "databases" / "test_memory.db"
            engine = MemoryEngine(db_path, bus)
            self.log_result("Memory Engine Initialization", True, "MemoryEngine initialized successfully")
            return True
        except Exception as e:
            self.log_result("Memory Engine Initialization", False, str(e))
            return False
    
    def test_memory_engine_store(self):
        """Test memory engine can store chunks"""
        try:
            from memory.engine import MemoryEngine
            bus = EventBus()
            db_path = self.root / "databases" / "test_memory.db"
            engine = MemoryEngine(db_path, bus)
            result = engine.store("Test chunk content", "test", ["test_tag"])
            if result and result.get("ok"):
                self.log_result("Memory Engine Store", True, f"Chunk stored with ID: {result.get('id')}")
                return True
            else:
                self.log_result("Memory Engine Store", False, f"Store failed: {result}")
                return False
        except Exception as e:
            self.log_result("Memory Engine Store", False, str(e))
            return False
    
    def test_memory_engine_search(self):
        """Test memory engine can search chunks"""
        try:
            from memory.engine import MemoryEngine
            bus = EventBus()
            db_path = self.root / "databases" / "test_memory.db"
            engine = MemoryEngine(db_path, bus)
            results = engine.search("test", 5)
            if results and isinstance(results, list):
                self.log_result("Memory Engine Search", True, f"Search returned {len(results)} results")
                return True
            else:
                self.log_result("Memory Engine Search", False, f"Search returned invalid: {results}")
                return False
        except Exception as e:
            self.log_result("Memory Engine Search", False, str(e))
            return False
    
    def test_agents_runtime_import(self):
        """Test agents runtime can be imported"""
        try:
            from agents.runtime import AgentRuntime, BaseAgent, PlannerAgent
            self.log_result("Agents Runtime Import", True, "AgentRuntime and agents imported successfully")
            return True
        except Exception as e:
            self.log_result("Agents Runtime Import", False, str(e))
            return False
    
    def test_agents_runtime_initialization(self):
        """Test agents runtime can be initialized"""
        try:
            from agents.runtime import AgentRuntime
            from memory.engine import MemoryEngine
            bus = EventBus()
            db_path = self.root / "databases" / "test_memory.db"
            memory = MemoryEngine(db_path, bus)
            
            async def voice_handler(task):
                return {"ok": True}
            
            async def vision_handler(task):
                return {"ok": True}
            
            async def workflow_handler(task):
                return {"ok": True}
            
            runtime = AgentRuntime(bus, memory, voice_handler, vision_handler, workflow_handler)
            self.log_result("Agents Runtime Initialization", True, "AgentRuntime initialized successfully")
            return True
        except Exception as e:
            self.log_result("Agents Runtime Initialization", False, str(e))
            return False
    
    def test_automation_engine_import(self):
        """Test automation engine can be imported"""
        try:
            from automation.engine import AutomationEngine
            self.log_result("Automation Engine Import", True, "AutomationEngine imported successfully")
            return True
        except Exception as e:
            self.log_result("Automation Engine Import", False, str(e))
            return False
    
    def test_automation_engine_initialization(self):
        """Test automation engine can be initialized"""
        try:
            from automation.engine import AutomationEngine
            from vision.engine import VisionEngine
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
            from automation.engine import AutomationEngine
            from vision.engine import VisionEngine
            bus = EventBus()
            captures_path = self.root / "logs" / "captures"
            vision = VisionEngine(captures_path, bus)
            engine = AutomationEngine(bus, vision)
            status = engine.status()
            if status and isinstance(status, dict):
                self.log_result("Automation Engine Status", True, f"Status returned: {status}")
                return True
            else:
                self.log_result("Automation Engine Status", False, f"Status returned invalid: {status}")
                return False
        except Exception as e:
            self.log_result("Automation Engine Status", False, str(e))
            return False
    
    def test_workflows_engine_import(self):
        """Test workflows engine can be imported"""
        try:
            from workflows.engine import WorkflowEngine
            self.log_result("Workflows Engine Import", True, "WorkflowEngine imported successfully")
            return True
        except Exception as e:
            self.log_result("Workflows Engine Import", False, str(e))
            return False
    
    def test_workflows_engine_initialization(self):
        """Test workflows engine can be initialized"""
        try:
            from workflows.engine import WorkflowEngine
            bus = EventBus()
            db_path = self.root / "databases" / "test_workflows.db"
            engine = WorkflowEngine(db_path, bus)
            self.log_result("Workflows Engine Initialization", True, "WorkflowEngine initialized successfully")
            return True
        except Exception as e:
            self.log_result("Workflows Engine Initialization", False, str(e))
            return False
    
    def test_ai_lab_import(self):
        """Test AI lab can be imported"""
        try:
            from ai_lab.agent_creator import AgentCreator
            self.log_result("AI Lab Import", True, "AgentCreator imported successfully")
            return True
        except Exception as e:
            self.log_result("AI Lab Import", False, str(e))
            return False
    
    def test_ai_lab_initialization(self):
        """Test AI lab can be initialized"""
        try:
            from ai_lab.agent_creator import AgentCreator
            bus = EventBus()
            sandbox_path = self.root / "ai_lab_sandbox"
            registry_path = self.root / "databases" / "test_generated_agents.json"
            creator = AgentCreator(sandbox_path, registry_path, bus)
            self.log_result("AI Lab Initialization", True, "AgentCreator initialized successfully")
            return True
        except Exception as e:
            self.log_result("AI Lab Initialization", False, str(e))
            return False
    
    def test_api_import(self):
        """Test API app can be imported"""
        try:
            from api.app import app
            self.log_result("API Import", True, "FastAPI app imported successfully")
            return True
        except Exception as e:
            self.log_result("API Import", False, str(e))
            return False
    
    def test_monitoring_import(self):
        """Test monitoring system can be imported"""
        try:
            from monitoring.system_monitor import SystemMonitor
            self.log_result("Monitoring Import", True, "SystemMonitor imported successfully")
            return True
        except Exception as e:
            self.log_result("Monitoring Import", False, str(e))
            return False
    
    def test_plugins_directory(self):
        """Test plugins directory exists"""
        try:
            plugins_path = self.root / "nexora_os" / "plugins"
            if plugins_path.exists():
                self.log_result("Plugins Directory", True, f"Plugins directory exists: {plugins_path}")
                return True
            else:
                self.log_result("Plugins Directory", False, f"Plugins directory not found: {plugins_path}")
                return False
        except Exception as e:
            self.log_result("Plugins Directory", False, str(e))
            return False
    
    def test_models_directory(self):
        """Test models directory exists"""
        try:
            models_path = self.root / "nexora_os" / "models"
            if models_path.exists():
                self.log_result("Models Directory", True, f"Models directory exists: {models_path}")
                return True
            else:
                self.log_result("Models Directory", False, f"Models directory not found: {models_path}")
                return False
        except Exception as e:
            self.log_result("Models Directory", False, str(e))
            return False
    
    def test_databases_directory(self):
        """Test databases directory exists"""
        try:
            databases_path = self.root / "nexora_os" / "databases"
            if databases_path.exists():
                self.log_result("Databases Directory", True, f"Databases directory exists: {databases_path}")
                return True
            else:
                self.log_result("Databases Directory", False, f"Databases directory not found: {databases_path}")
                return False
        except Exception as e:
            self.log_result("Databases Directory", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all backend module tests"""
        print("=" * 60)
        print("BACKEND MODULES VERIFICATION TESTS")
        print("=" * 60)
        print()
        
        # Voice Engine Tests
        print("--- Voice Engine ---")
        self.test_voice_engine_import()
        self.test_voice_engine_initialization()
        self.test_voice_engine_health()
        
        # Vision Engine Tests
        print("\n--- Vision Engine ---")
        self.test_vision_engine_import()
        self.test_vision_engine_initialization()
        self.test_vision_engine_health()
        
        # Memory Engine Tests
        print("\n--- Memory Engine ---")
        self.test_memory_engine_import()
        self.test_memory_engine_initialization()
        self.test_memory_engine_store()
        self.test_memory_engine_search()
        
        # Agents Tests
        print("\n--- Agents ---")
        self.test_agents_runtime_import()
        self.test_agents_runtime_initialization()
        
        # Automation Engine Tests
        print("\n--- Automation Engine ---")
        self.test_automation_engine_import()
        self.test_automation_engine_initialization()
        self.test_automation_engine_status()
        
        # Workflows Engine Tests
        print("\n--- Workflows Engine ---")
        self.test_workflows_engine_import()
        self.test_workflows_engine_initialization()
        
        # AI Lab Tests
        print("\n--- AI Lab ---")
        self.test_ai_lab_import()
        self.test_ai_lab_initialization()
        
        # API Tests
        print("\n--- API ---")
        self.test_api_import()
        
        # Monitoring Tests
        print("\n--- Monitoring ---")
        self.test_monitoring_import()
        
        # Directory Tests
        print("\n--- Directories ---")
        self.test_plugins_directory()
        self.test_models_directory()
        self.test_databases_directory()
        
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
            print("\n✓ All backend module tests passed!")
        else:
            print("\n✗ Some tests failed. Review details above.")
        
        return passed == total


def main():
    tester = TestBackendModules()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
