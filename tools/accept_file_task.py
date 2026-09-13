"""Real API acceptance probe for filesystem task execution."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    child = """
import sys, threading, uvicorn
from pathlib import Path
from nexora_os.backend.api import app as api
api.runtime = api.NexoraRuntime(Path(sys.argv[1]))
server = uvicorn.Server(uvicorn.Config(api.app, host='127.0.0.1', port=int(sys.argv[2]), log_level='warning'))
def stop():
    sys.stdin.readline()
    server.should_exit = True
threading.Thread(target=stop, daemon=True).start()
server.run()
"""

    def request(port: int, path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response)

    with tempfile.TemporaryDirectory(prefix="jarvis-file-task-") as data:
        root = Path(data)
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
            process = subprocess.Popen(
                [sys.executable, "-c", child, data, str(port)],
                cwd=repo,
                stdin=subprocess.PIPE,
                stdout=output,
                stderr=output,
                text=True,
            )
            try:
                deadline = time.monotonic() + 60
                while True:
                    try:
                        request(port, "/status")
                        break
                    except (OSError, urllib.error.URLError):
                        if process.poll() is not None or time.monotonic() > deadline:
                            output.seek(0)
                            raise RuntimeError(output.read()[-4000:])
                        time.sleep(0.2)

                command = 'Create a file called test.py containing print("hello from acceptance")'
                created = request(port, "/process", {"input": command, "context": {"speak": False}})
                target = root / "test.py"
                assert created.get("ok"), created
                assert target.exists(), created
                assert target.read_text(encoding="utf-8") == 'print("hello from acceptance")\n'
                assert created.get("verification", {}).get("content_matches") is True
                assert created.get("permission_checked") is True

                read_back = request(port, "/process", {"input": "read file test.py", "context": {"speak": False}})
                assert read_back.get("ok"), read_back
                assert "hello from acceptance" in str(read_back.get("content") or read_back.get("message"))

                blocked = request(
                    port,
                    "/connectors/filesystem/execute",
                    {
                        "input": "",
                        "context": {
                            "action": "write_file",
                            "path": str(root.parent / "outside-jarvis.txt"),
                            "content": "must not be written",
                        },
                    },
                )
                assert blocked.get("ok") is False, blocked
                assert "outside allowed project root" in blocked.get("error", ""), blocked

                print(json.dumps({
                    "created": str(target),
                    "bytes": target.stat().st_size,
                    "verified_read_back": True,
                    "outside_root_blocked": True,
                }))
            finally:
                if process.poll() is None:
                    process.communicate("stop\n", timeout=30)
                assert process.returncode == 0, f"Server exit: {process.returncode}"
                print("Application shutdown: clean")


if __name__ == "__main__":
    main()
