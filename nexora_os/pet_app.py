from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKEND = "http://127.0.0.1:7474"


@dataclass(slots=True)
class PetState:
    mode: str = "idle"
    message: str = "Jarvis is ready"
    backend_online: bool = False
    cpu: float = 0.0
    ram: float = 0.0
    active_agents: int = 0
    event_errors: int = 0
    last_updated: float = 0.0


def fetch_status(base_url: str, timeout: float = 0.8) -> PetState:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/status", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return PetState(mode="offline", message="Jarvis backend is offline", backend_online=False, last_updated=time.time())

    cpu = float(payload.get("cpu") or 0)
    ram = float(payload.get("ram") or 0)
    event_errors = int(payload.get("event_errors") or 0)
    agents = int(payload.get("active_agents") or 0)
    tasks = int(payload.get("tasks") or 0)
    voice_state = str(payload.get("voice_state") or "idle").lower()

    if event_errors:
        mode = "error"
        message = f"{event_errors} runtime error event(s)"
    elif voice_state not in {"idle", "stopped", ""}:
        mode = "speaking" if "speak" in voice_state else "listening"
        message = f"Voice: {voice_state}"
    elif tasks or agents:
        mode = "thinking"
        message = f"{agents} agent(s), {tasks} queued task(s)"
    else:
        mode = "idle"
        message = f"CPU {cpu:.0f}%  RAM {ram:.0f}%"

    return PetState(
        mode=mode,
        message=message,
        backend_online=True,
        cpu=cpu,
        ram=ram,
        active_agents=agents,
        event_errors=event_errors,
        last_updated=time.time(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis floating Windows pet")
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    parser.add_argument("--smoke-test", action="store_true", help="Create the pet UI, render one frame, and exit")
    parser.add_argument("--screenshot", type=Path, help="Save a screenshot during smoke test")
    args = parser.parse_args()

    try:
        from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
        from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPen, QRadialGradient
        from PySide6.QtWidgets import QApplication, QMenu, QWidget
    except ImportError as exc:
        print("PySide6 is required for the Jarvis Windows pet.")
        print("Run: python -m pip install -r nexora_os\\requirements-desktop.txt")
        print(exc)
        return 1

    class JarvisPet(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.state = fetch_status(args.backend)
            self.phase = 0.0
            self.drag_start: QPoint | None = None
            self.setWindowTitle("Jarvis Pet")
            self.setFixedSize(190, 210)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setMouseTracking(True)
            self.move(80, 120)

            self.animation_timer = QTimer(self)
            self.animation_timer.timeout.connect(self._tick)
            self.animation_timer.start(33)

            self.status_timer = QTimer(self)
            self.status_timer.timeout.connect(self._refresh_status)
            self.status_timer.start(1500)

        def _tick(self) -> None:
            self.phase = (self.phase + 0.055) % (math.tau)
            self.update()

        def _refresh_status(self) -> None:
            self.state = fetch_status(args.backend)
            self.update()

        def mousePressEvent(self, event: Any) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
            elif event.button() == Qt.MouseButton.RightButton:
                self._show_menu(event.globalPosition().toPoint())

        def mouseMoveEvent(self, event: Any) -> None:
            if self.drag_start is not None and event.buttons() & Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self.drag_start)
                event.accept()

        def mouseReleaseEvent(self, event: Any) -> None:
            self.drag_start = None
            event.accept()

        def mouseDoubleClickEvent(self, event: Any) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self._open_command_center()

        def _show_menu(self, position: QPoint) -> None:
            menu = QMenu(self)
            menu.addAction(QAction("Open Command Center", self, triggered=self._open_command_center))
            menu.addAction(QAction("Refresh Status", self, triggered=self._refresh_status))
            menu.addSeparator()
            menu.addAction(QAction("Quit Pet", self, triggered=QApplication.instance().quit))
            menu.exec(position)

        def _open_command_center(self) -> None:
            import subprocess

            launcher = ROOT / "run_project.cmd"
            if launcher.exists() and sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", "start", "", str(launcher)], cwd=str(ROOT))

        def paintEvent(self, event: Any) -> None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            colors = {
                "idle": (QColor(54, 211, 153), QColor(14, 165, 233)),
                "thinking": (QColor(250, 204, 21), QColor(14, 165, 233)),
                "listening": (QColor(34, 211, 238), QColor(59, 130, 246)),
                "speaking": (QColor(168, 85, 247), QColor(236, 72, 153)),
                "error": (QColor(248, 113, 113), QColor(249, 115, 22)),
                "offline": (QColor(148, 163, 184), QColor(71, 85, 105)),
            }
            c1, c2 = colors.get(self.state.mode, colors["idle"])

            bob = math.sin(self.phase) * 6
            pulse = 1.0 + (math.sin(self.phase * 2) * 0.035)
            cx, cy = 95, 86 + bob
            radius = 54 * pulse

            glow = QRadialGradient(cx, cy, radius * 1.6)
            glow.setColorAt(0.0, QColor(c1.red(), c1.green(), c1.blue(), 145))
            glow.setColorAt(0.55, QColor(c2.red(), c2.green(), c2.blue(), 70))
            glow.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - radius * 1.6, cy - radius * 1.6, radius * 3.2, radius * 3.2))

            body = QRadialGradient(cx - 16, cy - 18, radius * 1.25)
            body.setColorAt(0.0, QColor(255, 255, 255, 235))
            body.setColorAt(0.28, c1)
            body.setColorAt(1.0, c2)
            painter.setBrush(body)
            painter.setPen(QPen(QColor(255, 255, 255, 180), 2))
            painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

            painter.setBrush(QColor(5, 12, 24, 230))
            painter.setPen(Qt.PenStyle.NoPen)
            eye_y = cy - 10 + math.sin(self.phase * 1.7) * 2
            painter.drawEllipse(QRectF(cx - 24, eye_y, 11, 15))
            painter.drawEllipse(QRectF(cx + 13, eye_y, 11, 15))

            painter.setPen(QPen(QColor(5, 12, 24, 220), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            if self.state.mode == "error":
                painter.drawLine(int(cx - 16), int(cy + 23), int(cx + 16), int(cy + 16))
            elif self.state.mode == "offline":
                painter.drawLine(int(cx - 16), int(cy + 20), int(cx + 16), int(cy + 20))
            else:
                painter.drawArc(QRectF(cx - 20, cy + 8, 40, 24), 200 * 16, 140 * 16)

            painter.setPen(QPen(c1, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for i in range(8):
                angle = self.phase + i * math.tau / 8
                inner = radius + 10 + math.sin(self.phase * 1.5 + i) * 2
                outer = inner + 11
                painter.drawLine(
                    int(cx + math.cos(angle) * inner),
                    int(cy + math.sin(angle) * inner),
                    int(cx + math.cos(angle) * outer),
                    int(cy + math.sin(angle) * outer),
                )

            panel = QRectF(18, 155, 154, 38)
            painter.setBrush(QColor(3, 7, 18, 205))
            painter.setPen(QPen(QColor(255, 255, 255, 55), 1))
            painter.drawRoundedRect(panel, 8, 8)

            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            painter.setPen(QColor(240, 249, 255))
            painter.drawText(QRectF(24, 159, 142, 14), Qt.AlignmentFlag.AlignCenter, self.state.mode.upper())
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor(203, 213, 225))
            painter.drawText(QRectF(24, 174, 142, 14), Qt.AlignmentFlag.AlignCenter, self.state.message[:34])

    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis Pet")
    pet = JarvisPet()
    pet.show()

    if args.smoke_test:
        def finish_smoke() -> None:
            if args.screenshot:
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                pet.grab().save(str(args.screenshot))
            print(
                json.dumps(
                    {
                        "ok": True,
                        "mode": pet.state.mode,
                        "backend_online": pet.state.backend_online,
                        "size": [pet.width(), pet.height()],
                    }
                )
            )
            app.exit(0)

        QTimer.singleShot(900, finish_smoke)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
