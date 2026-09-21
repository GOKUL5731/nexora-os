from nexora_os.backend.brain.capability_registry import CapabilityRegistry
from nexora_os.backend.brain.tool_router import ToolRouter


def build_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register_capability(
        "connector.browser",
        "Browser Connector",
        "connector_manager",
        ["open_url", "search_web", "get_page_title"],
        risk_level="low",
    )
    registry.register_capability(
        "connector.filesystem",
        "Filesystem Connector",
        "connector_manager",
        ["read_file", "write_file", "delete_file"],
        permissions=["filesystem_read", "filesystem_write"],
        risk_level="high",
    )
    registry.register_capability(
        "knowledge.learn_retrieve",
        "Knowledge Manager",
        "knowledge_manager",
        ["learn", "study", "knowledge", "domain", "index", "retrieve"],
        risk_level="low",
    )
    registry.register_capability(
        "model.ollama",
        "Ollama Local Models",
        "llm",
        ["llm", "reasoning", "coding", "text_generation"],
        risk_level="low",
        available=False,
        health="unavailable",
    )
    return registry


def test_selects_registered_browser_capability() -> None:
    router = ToolRouter(build_registry())

    result = router.select_tool("open browser url https://example.com", [])

    assert result["ok"] is True
    assert result["tool"] == "connector.browser"
    assert result["capability_id"] == "connector.browser"
    assert result["provider"] == "connector_manager"
    assert result["risk_level"] == "low"
    assert result["requires_approval"] is False
    assert result["candidates"][0]["id"] == "connector.browser"


def test_delete_file_requires_approval_and_reports_permissions() -> None:
    router = ToolRouter(build_registry())

    result = router.select_tool("delete file called old.log", ["filesystem_read"])

    assert result["tool"] == "connector.filesystem"
    assert result["risk_level"] == "high"
    assert result["requires_approval"] is True
    assert result["missing_permissions"] == ["filesystem_write"]


def test_learning_routes_to_knowledge_manager() -> None:
    router = ToolRouter(build_registry())

    result = router.select_tool("learn FastAPI websocket architecture", [])

    assert result["tool"] == "knowledge.learn_retrieve"
    assert result["provider"] == "knowledge_manager"
