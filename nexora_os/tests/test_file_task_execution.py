import asyncio
from pathlib import Path

from nexora_os.backend.core.runtime import NexoraRuntime


def test_process_creates_file_with_verified_side_effect(tmp_path: Path):
    async def run():
        runtime = NexoraRuntime(tmp_path)
        await runtime.start()
        try:
            result = await runtime.process(
                'Create a file called test.py containing print("hello from regression")',
                {"speak": False},
            )
        finally:
            await runtime.shutdown()
        return result

    result = asyncio.run(run())
    target = tmp_path / "test.py"

    assert result["ok"] is True
    assert target.exists()
    assert target.read_text(encoding="utf-8") == 'print("hello from regression")\n'
    assert result["permission_checked"] is True
    assert result["verification"]["exists"] is True
    assert result["verification"]["is_file"] is True
    assert result["verification"]["content_matches"] is True


def test_filesystem_connector_blocks_paths_outside_runtime_root(tmp_path: Path):
    async def run():
        runtime = NexoraRuntime(tmp_path)
        await runtime.start()
        try:
            connector = runtime.connector_manager.get("filesystem")
            return connector.execute(
                "write_file",
                {
                    "path": str(tmp_path.parent / "outside-jarvis-regression.txt"),
                    "content": "blocked",
                },
            )
        finally:
            await runtime.shutdown()

    result = asyncio.run(run())
    assert result["ok"] is False
    assert "outside allowed project root" in result["error"]


def test_runtime_remembers_created_file_for_followup_open(tmp_path: Path, monkeypatch):
    opened: list[str] = []

    async def run():
        runtime = NexoraRuntime(tmp_path)
        await runtime.start()
        try:
            monkeypatch.setattr("nexora_os.backend.core.runtime.os.startfile", lambda path: opened.append(str(path)))
            created = await runtime.process(
                'Create a file called gokul.txt containing hello',
                {"speak": False, "session_id": "followup"},
            )
            summary = await runtime.process(
                "what did we do",
                {"speak": False, "session_id": "followup"},
            )
            opened_result = await runtime.process(
                "open the created file",
                {"speak": False, "session_id": "followup"},
            )
        finally:
            await runtime.shutdown()
        return created, summary, opened_result

    created, summary, opened_result = asyncio.run(run())

    target = tmp_path / "gokul.txt"
    assert created["ok"] is True
    assert target.exists()
    assert summary["ok"] is True
    assert "Create a file called gokul.txt" in summary["message"]
    assert opened_result["ok"] is True
    assert opened == [str(target)]


def test_runtime_opens_chatgpt_and_types_without_ui_action_failure(tmp_path: Path):
    async def run():
        runtime = NexoraRuntime(tmp_path)
        await runtime.start()
        try:
            browser = runtime.connector_manager.get("browser")
            original_execute = browser.execute

            def fake_browser_execute(action, params):
                if action == "open_url":
                    return {"ok": True, "url": params["url"], "message": f"Opened {params['url']}"}
                return original_execute(action, params)

            browser.execute = fake_browser_execute
            runtime.automation._type_text_keyboard_fallback = lambda text: {"ok": True}
            return await runtime.process(
                "open chatgpt and type hi",
                {"speak": False, "session_id": "chatgpt"},
            )
        finally:
            await runtime.shutdown()

    result = asyncio.run(run())

    assert result["ok"] is True
    assert result["url"] == "https://chatgpt.com"
    assert result["typed_text"] == "hi"
    assert result["verification"]["typed_text_sent"] is True
    assert "execute_ui_action" not in result["message"]
