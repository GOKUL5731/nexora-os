from __future__ import annotations

import socket
import argparse
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
    try:
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
    finally:
        stdout.close()
        stderr.close()


def _start_pet() -> subprocess.Popen | None:
    logs = ROOT / "nexora_os" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout = open(logs / "pet.out.log", "a", encoding="utf-8")
    stderr = open(logs / "pet.err.log", "a", encoding="utf-8")
    try:
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "nexora_os.pet_app",
                "--backend",
                URL,
                "--dashboard-title",
                "Jarvis Command Center",
                "--dashboard-url",
                URL,
            ],
            cwd=ROOT,
            stdout=stdout,
            stderr=stderr,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    finally:
        stdout.close()
        stderr.close()


def _stop_backend(backend: subprocess.Popen | None) -> None:
    if backend and backend.poll() is None:
        backend.terminate()
        try:
            backend.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend.kill()
            backend.wait(timeout=5)


def _stop_process(process: subprocess.Popen | None) -> None:
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> int:
    global PORT, URL
    if not _port_is_open(PORT):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", PORT))
            except OSError:
                probe.bind(("127.0.0.1", 0))
                PORT = probe.getsockname()[1]
                URL = f"http://127.0.0.1:{PORT}"
                print(f"Default port unavailable. Backend: {URL}")
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true", help="Open the real desktop UI, verify rendered content, then exit")
    parser.add_argument("--screenshot", type=Path, help="Save the rendered desktop window during a smoke test")
    parser.add_argument("--no-pet", action="store_true", help="Do not launch the floating Jarvis pet")
    args = parser.parse_args()
    try:
        from PySide6.QtCore import QUrl, QTimer
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
        _stop_backend(backend)
        return 1

    pet = None if args.no_pet or args.smoke_test else _start_pet()

    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis")

    window = QMainWindow()
    window.setWindowTitle("Jarvis Command Center")
    window.resize(1440, 900)

    view = QWebEngineView()
    if args.smoke_test:
        def check_content(ok: bool) -> None:
            if not ok:
                app.exit(1)
                return
            def inspected(text: str) -> None:
                valid = isinstance(text, str) and "LIVE TELEMETRY" in text
                print(f"Desktop rendered content: {len(text or '')} characters; passed={valid}")
                if args.screenshot:
                    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                    if not window.grab().save(str(args.screenshot)):
                        app.exit(1)
                        return
                app.exit(0 if valid else 1)
            QTimer.singleShot(10000, lambda: view.page().runJavaScript("document.body.innerText", inspected))
        view.loadFinished.connect(check_content)
        QTimer.singleShot(30000, lambda: app.exit(2))
    view.setUrl(QUrl(URL))
    window.setCentralWidget(view)
    window.showMaximized()

    try:
        return app.exec()
    finally:
        _stop_process(pet)
        _stop_backend(backend)


if __name__ == "__main__":
    raise SystemExit(main())
