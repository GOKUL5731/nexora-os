import pytest

from backend.computer.app_adapters.antigravity import AntigravityAdapter
from backend.computer.app_adapters.codex import CodexAdapter
from backend.computer.app_adapters.cursor import CursorAdapter


@pytest.mark.parametrize("adapter_type", [CursorAdapter, CodexAdapter, AntigravityAdapter])
def test_adapter_does_not_claim_missing_application_is_installed(monkeypatch, adapter_type):
    monkeypatch.setattr("shutil.which", lambda _: None)
    adapter = adapter_type()
    result = adapter.discover()
    assert result["installed"] is False
    assert result["running"] is False
    assert result["capabilities"]["send_prompt"] is False


@pytest.mark.asyncio
async def test_prompt_transport_is_explicitly_unavailable():
    result = await CursorAdapter().send_prompt("do work")
    assert result["ok"] is False
    assert result["status"] == "UNAVAILABLE"
    assert result["error"] == "prompt_transport_not_implemented"
