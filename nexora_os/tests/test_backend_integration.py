"""
Backend Integration Test
Tests that the backend can start and respond to basic API requests
"""
import subprocess
import time
import requests
import sys
import signal
from pathlib import Path

class TestBackendIntegration:
    def __init__(self):
        self.results = []
        self.backend_process = None
        self.base_url = "http://127.0.0.1:7474"
        
    def log_result(self, test_name: str, passed: bool, details: str = ""):
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append({"test": test_name, "passed": passed, "details": details})
        print(f"{status}: {test_name}")
        if details:
            print(f"  Details: {details}")
    
    def start_backend(self):
        """Start the backend server"""
        try:
            backend_dir = Path(__file__).parent.parent / "backend"
            self.backend_process = subprocess.Popen(
                [sys.executable, "-m", "nexora_os.backend.api.app"],
                cwd=str(Path(__file__).parent.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for backend to start
            for i in range(30):  # 30 seconds timeout
                try:
                    response = requests.get(f"{self.base_url}/status", timeout=2)
                    if response.status_code == 200:
                        self.log_result("Backend Startup", True, "Backend started successfully")
                        return True
                except:
                    time.sleep(1)
            
            self.log_result("Backend Startup", False, "Backend did not start within timeout")
            return False
        except Exception as e:
            self.log_result("Backend Startup", False, str(e))
            return False
    
    def stop_backend(self):
        """Stop the backend server"""
        if self.backend_process:
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
    
    def test_status_endpoint(self):
        """Test /status endpoint"""
        try:
            response = requests.get(f"{self.base_url}/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log_result("Status Endpoint", True, f"Status: {data.get('status')}")
                return True
            else:
                self.log_result("Status Endpoint", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Status Endpoint", False, str(e))
            return False
    
    def test_health_endpoint(self):
        """Test /health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log_result("Health Endpoint", True, f"Health check passed")
                return True
            else:
                self.log_result("Health Endpoint", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Health Endpoint", False, str(e))
            return False
    
    def test_memory_endpoint(self):
        """Test /memory endpoint"""
        try:
            response = requests.get(f"{self.base_url}/memory", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log_result("Memory Endpoint", True, f"Memory chunks: {len(data.get('chunks', []))}")
                return True
            else:
                self.log_result("Memory Endpoint", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Memory Endpoint", False, str(e))
            return False
    
    def test_agents_endpoint(self):
        """Test /agents endpoint"""
        try:
            response = requests.get(f"{self.base_url}/agents", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log_result("Agents Endpoint", True, f"Agents: {len(data.get('agents', []))}")
                return True
            else:
                self.log_result("Agents Endpoint", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Agents Endpoint", False, str(e))
            return False
    
    def test_voice_status_endpoint(self):
        """Test /voice/status endpoint"""
        try:
            response = requests.get(f"{self.base_url}/voice/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log_result("Voice Status Endpoint", True, f"Voice status: {data.get('status')}")
                return True
            else:
                self.log_result("Voice Status Endpoint", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Voice Status Endpoint", False, str(e))
            return False
    
    def test_vision_status_endpoint(self):
        """Test /vision/status endpoint"""
        try:
            response = requests.get(f"{self.base_url}/vision/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log_result("Vision Status Endpoint", True, f"Vision status: {data.get('status')}")
                return True
            else:
                self.log_result("Vision Status Endpoint", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Vision Status Endpoint", False, str(e))
            return False
    
    def test_automation_endpoint(self):
        """Test /automation endpoint"""
        try:
            response = requests.get(f"{self.base_url}/automation", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log_result("Automation Endpoint", True, f"Actions: {len(data.get('actions', []))}")
                return True
            else:
                self.log_result("Automation Endpoint", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Automation Endpoint", False, str(e))
            return False
    
    def test_workflows_endpoint(self):
        """Test /workflows endpoint"""
        try:
            response = requests.get(f"{self.base_url}/workflows", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log_result("Workflows Endpoint", True, f"Workflows: {len(data.get('workflows', []))}")
                return True
            else:
                self.log_result("Workflows Endpoint", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Workflows Endpoint", False, str(e))
            return False
    
    def test_process_endpoint(self):
        """Test /process endpoint"""
        try:
            response = requests.post(f"{self.base_url}/process", json={"input": "test"}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_result("Process Endpoint", True, f"Response type: {data.get('type')}")
                return True
            else:
                self.log_result("Process Endpoint", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Process Endpoint", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all backend integration tests"""
        print("=" * 60)
        print("BACKEND INTEGRATION TESTS")
        print("=" * 60)
        print()
        
        # Start backend
        if not self.start_backend():
            print("\n✗ Backend failed to start. Aborting tests.")
            return False
        
        print()
        
        # Run API tests
        print("--- API Endpoint Tests ---")
        self.test_status_endpoint()
        self.test_health_endpoint()
        self.test_memory_endpoint()
        self.test_agents_endpoint()
        self.test_voice_status_endpoint()
        self.test_vision_status_endpoint()
        self.test_automation_endpoint()
        self.test_workflows_endpoint()
        self.test_process_endpoint()
        
        # Stop backend
        self.stop_backend()
        
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
            print("\n✓ All backend integration tests passed!")
        else:
            print("\n✗ Some tests failed. Review details above.")
        
        return passed == total


def main():
    tester = TestBackendIntegration()
    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        tester.stop_backend()
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest error: {e}")
        tester.stop_backend()
        sys.exit(1)


if __name__ == "__main__":
    main()
