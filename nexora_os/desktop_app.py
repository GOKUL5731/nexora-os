from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PORT = 7474
URL = f"http://127.0.0.1:{PORT}"
ROOT = Path(__file__).resolve().parents[1]


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_backend(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{URL}/status", timeout=1.0) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.35)
    return False


def _start_backend() -> subprocess.Popen | None:
    if _port_is_open(PORT):
        return None
    logs = ROOT / "nexora_os" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout = open(logs / "desktop_backend.out.log", "a", encoding="utf-8")
    stderr = open(logs / "desktop_backend.err.log", "a", encoding="utf-8")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "nexora_os.backend.api.app",
            "--serve-ui",
            "--port",
            str(PORT),
        ],
        cwd=ROOT,
        stdout=stdout,
        stderr=stderr,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def main() -> int:
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QApplication, QMainWindow
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except ImportError as exc:
        print("PySide6 with QtWebEngine is required for the Windows desktop app.")
        print("Run: python -m pip install -r nexora_os\\requirements-desktop.txt")
        print(exc)
        return 1

    backend = _start_backend()
    if not _wait_for_backend():
        print("NEXORA backend did not start. Check nexora_os\\logs\\desktop_backend.err.log")
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName("NEXORA OS")

    window = QMainWindow()
    window.setWindowTitle("NEXORA OS Command Center")
    window.resize(1440, 900)

    view = QWebEngineView()
    view.setUrl(QUrl(URL))
    window.setCentralWidget(view)
    window.showMaximized()

    try:
        return app.exec()
    finally:
        if backend and backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend.kill()


if __name__ == "__main__":
    raise SystemExit(main())
