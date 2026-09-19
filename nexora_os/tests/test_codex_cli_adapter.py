import pytest

from backend.computer.app_adapters.codex import CodexAdapter


@pytest.mark.asyncio
async def test_codex_adapter_requires_real_workspace_before_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda _: "C:/codex.exe")
    adapter = CodexAdapter()
    result = await adapter.send_prompt("inspect")
    assert result["ok"] is False
    assert result["error"] == "workspace_not_attached"


def test_codex_cli_capability_is_reported(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "C:/codex.exe")
    result = CodexAdapter().discover()
    assert result["codex_cli"] is True
    assert result["capabilities"]["send_prompt"] is True
