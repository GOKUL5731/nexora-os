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
