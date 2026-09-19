from backend.core.event_bus import EventBus
from backend.knowledge.manager import KnowledgeManager
from backend.memory.engine import MemoryEngine


def test_learning_creates_persistent_graph_nodes_and_edges(tmp_path):
    bus = EventBus()
    memory = MemoryEngine(tmp_path / "memory.db", bus)
    manager = KnowledgeManager(tmp_path / "knowledge.db", memory, bus)
    result = manager.learn_domain("Python", [{"title": "Python testing", "content": "pytest tests", "source": "local", "tags": ["testing"]}])
    assert result["ok"] is True
    graph = manager.graph()
    names = {node["name"] for node in graph["nodes"]}
    assert "Python" in names
    assert "testing" in names
    assert any(edge["relationship"] == "RELATED_TO" for edge in graph["edges"])
