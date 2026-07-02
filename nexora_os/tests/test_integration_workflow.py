"""
Workflow Engine Integration Test
Tests workflow creation, execution, storage, logging
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from nexora_os.backend.core.event_bus import EventBus
from nexora_os.backend.workflows.engine import WorkflowEngine


class TestWorkflowIntegration:
    def __init__(self):
        self.results = []
        self.root = Path(__file__).parent.parent.parent
        
    def log_result(self, test_name: str, passed: bool, details: str = ""):
        status = "✓ PASS" if passed else "✗ FAIL"
        self.results.append({"test": test_name, "passed": passed, "details": details})
        print(f"{status}: {test_name}")
        if details:
            print(f"  Details: {details}")
    
    def test_workflow_engine_initialization(self):
        """Test workflow engine can be initialized"""
        try:
            bus = EventBus()
            db_path = self.root / "databases" / "test_workflows.db"
            engine = WorkflowEngine(db_path, bus)
            self.log_result("Workflow Engine Initialization", True, "WorkflowEngine initialized successfully")
            return True
        except Exception as e:
            self.log_result("Workflow Engine Initialization", False, str(e))
            return False
    
    def test_workflow_engine_health(self):
        """Test workflow engine health check"""
        try:
            bus = EventBus()
            db_path = self.root / "databases" / "test_workflows.db"
            engine = WorkflowEngine(db_path, bus)
            health = engine.health()
            if health and isinstance(health, dict):
                self.log_result("Workflow Engine Health", True, f"Health check returned: {health}")
                return True
            else:
                self.log_result("Workflow Engine Health", False, f"Health check returned invalid: {health}")
                return False
        except Exception as e:
            self.log_result("Workflow Engine Health", False, str(e))
            return False
    
    async def test_workflow_creation(self):
        """Test workflow graph creation"""
        try:
            bus = EventBus()
            db_path = self.root / "databases" / "test_workflows.db"
            engine = WorkflowEngine(db_path, bus)
            
            # Create a simple workflow graph
            graph = {
                "nodes": [
                    {"id": "1", "type": "memory_save", "data": {"text": "Test workflow"}},
                    {"id": "2", "type": "wait", "data": {}}
                ],
                "edges": [
                    {"from": "1", "to": "2"}
                ]
            }
            
            result = await engine.save_graph("test_workflow", graph)
            if result.get("ok"):
                self.log_result("Workflow Creation", True, f"Workflow created: {result.get('id', '')}")
                return True
            else:
                self.log_result("Workflow Creation", False, f"Workflow creation failed: {result.get('error', 'Unknown')}")
                return False
        except Exception as e:
            self.log_result("Workflow Creation", False, str(e))
            return False
    
    async def test_workflow_execution(self):
        """Test workflow execution"""
        try:
            bus = EventBus()
            db_path = self.root / "databases" / "test_workflows.db"
            engine = WorkflowEngine(db_path, bus)
            
            # Create and execute a simple workflow
            graph = {
                "nodes": [
                    {"id": "1", "type": "memory_save", "data": {"text": "Test execution"}},
                    {"id": "2", "type": "wait", "data": {}}
                ],
                "edges": [
                    {"from": "1", "to": "2"}
                ]
            }
            
            await engine.save_graph("test_exec", graph)
            result = await engine.run("test_exec")
            
            if result.get("ok"):
                self.log_result("Workflow Execution", True, f"Workflow executed: {result.get('status', '')}")
                return True
            else:
                self.log_result("Workflow Execution", False, f"Workflow execution failed: {result.get('error', 'Unknown')}")
                return False
        except Exception as e:
            self.log_result("Workflow Execution", False, str(e))
            return False
    
    async def test_workflow_list(self):
        """Test listing workflows"""
        try:
            bus = EventBus()
            db_path = self.root / "databases" / "test_workflows.db"
            engine = WorkflowEngine(db_path, bus)
            
            workflows = engine.list()
            if isinstance(workflows, list):
                self.log_result("Workflow List", True, f"Found {len(workflows)} workflows")
                return True
            else:
                self.log_result("Workflow List", False, f"Invalid workflow list: {workflows}")
                return False
        except Exception as e:
            self.log_result("Workflow List", False, str(e))
            return False
    
    async def test_workflow_graph_retrieval(self):
        """Test retrieving workflow graphs"""
        try:
            bus = EventBus()
            db_path = self.root / "databases" / "test_workflows.db"
            engine = WorkflowEngine(db_path, bus)
            
            graphs = engine.graphs()
            if isinstance(graphs, list):
                self.log_result("Workflow Graph Retrieval", True, f"Retrieved {len(graphs)} graphs")
                return True
            else:
                self.log_result("Workflow Graph Retrieval", False, f"Invalid graphs: {graphs}")
                return False
        except Exception as e:
            self.log_result("Workflow Graph Retrieval", False, str(e))
            return False
    
    async def run_all_tests(self):
        """Run all workflow integration tests"""
        print("=" * 60)
        print("WORKFLOW ENGINE INTEGRATION TESTS")
        print("=" * 60)
        print()
        
        # Synchronous tests
        print("--- Workflow Engine Tests ---")
        self.test_workflow_engine_initialization()
        self.test_workflow_engine_health()
        
        # Async tests
        print("\n--- Workflow Pipeline Tests ---")
        await self.test_workflow_creation()
        await self.test_workflow_execution()
        await self.test_workflow_list()
        await self.test_workflow_graph_retrieval()
        
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
            print("\n✓ All workflow integration tests passed!")
        else:
            print("\n✗ Some tests failed. Review details above.")
        
        return passed == total


async def main():
    tester = TestWorkflowIntegration()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
