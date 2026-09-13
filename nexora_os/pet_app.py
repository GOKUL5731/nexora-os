from __future__ import annotations

import argparse
import concurrent.futures
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
    parser.add_argument("--dashboard-title", default="Jarvis Command Center")
    parser.add_argument("--dashboard-url", default="")
    parser.add_argument("--roam", action="store_true", help="Start with gentle desktop roaming enabled")
    parser.add_argument("--smoke-test", action="store_true", help="Create the pet UI, render one frame, and exit")
    parser.add_argument("--screenshot", type=Path, help="Save a screenshot during smoke test")
    args = parser.parse_args()

    try:
        from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, QUrl
        from PySide6.QtGui import (
            QAction,
            QColor,
            QDesktopServices,
            QFont,
            QPainter,
            QPainterPath,
            QPen,
            QPixmap,
            QRadialGradient,
            QTransform,
        )
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
            self.press_pos: QPoint | None = None
            self.roam_enabled = bool(args.roam)
            self.roam_x = 80.0
            self.roam_y = 120.0
            self.roam_vx = 0.85
            self.robot = QPixmap(str(ROOT / "nexora_os" / "assets" / "jarvis_robot_pet.png"))
            self.robot_frames = self._build_robot_frames()
            self.status_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="jarvis-pet-status")
            self.status_future: concurrent.futures.Future[PetState] | None = None
            self.setWindowTitle("Jarvis Pet")
            self.setFixedSize(230, 292)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setMouseTracking(True)
            self.move(int(self.roam_x), int(self.roam_y))

            self.animation_timer = QTimer(self)
            self.animation_timer.timeout.connect(self._tick)
            self.animation_timer.start(33)

            self.status_timer = QTimer(self)
            self.status_timer.timeout.connect(self._request_status)
            self.status_timer.start(1500)
            self.future_timer = QTimer(self)
            self.future_timer.timeout.connect(self._collect_status)
            self.future_timer.start(120)

        def _build_robot_frames(self) -> list[QPixmap]:
            if self.robot.isNull():
                return []
            base = self.robot.scaled(
                160,
                210,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            frames: list[QPixmap] = []
            for index in range(24):
                angle = math.sin((index / 24) * math.tau) * 3.5
                frames.append(base.transformed(QTransform().rotate(angle), Qt.TransformationMode.SmoothTransformation))
            return frames

        def _tick(self) -> None:
            self.phase = (self.phase + 0.052) % (math.tau)
            if self.roam_enabled and self.drag_start is None:
                self._roam_step()
            self.update()

        def _refresh_status(self) -> None:
            self.state = fetch_status(args.backend)
            self.update()

        def _request_status(self) -> None:
            if self.status_future and not self.status_future.done():
                return
            self.status_future = self.status_pool.submit(fetch_status, args.backend)

        def _collect_status(self) -> None:
            if not self.status_future or not self.status_future.done():
                return
            try:
                self.state = self.status_future.result()
            except Exception:
                self.state = PetState(mode="offline", message="Jarvis backend is offline", backend_online=False, last_updated=time.time())
            finally:
                self.status_future = None
            self.update()

        def _roam_step(self) -> None:
            screen = QApplication.primaryScreen()
            if screen is None:
                return
            bounds = screen.availableGeometry()
            speed = 1.0 if self.state.mode in {"idle", "offline"} else 1.7
            self.roam_x += self.roam_vx * speed
            self.roam_y += math.sin(self.phase * 0.7) * 0.35
            if self.roam_x < bounds.left() or self.roam_x + self.width() > bounds.right():
                self.roam_vx *= -1
                self.roam_x = max(bounds.left(), min(self.roam_x, bounds.right() - self.width()))
            self.roam_y = max(bounds.top(), min(self.roam_y, bounds.bottom() - self.height()))
            self.move(int(round(self.roam_x)), int(round(self.roam_y)))

        def mousePressEvent(self, event: Any) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self.press_pos = event.globalPosition().toPoint()
                event.accept()
            elif event.button() == Qt.MouseButton.RightButton:
                self._show_menu(event.globalPosition().toPoint())

        def mouseMoveEvent(self, event: Any) -> None:
            if self.drag_start is not None and event.buttons() & Qt.MouseButton.LeftButton:
                next_pos = event.globalPosition().toPoint() - self.drag_start
                self.roam_x = float(next_pos.x())
                self.roam_y = float(next_pos.y())
                self.move(next_pos)
                event.accept()

        def mouseReleaseEvent(self, event: Any) -> None:
            if event.button() == Qt.MouseButton.LeftButton and self.press_pos is not None:
                moved = event.globalPosition().toPoint() - self.press_pos
                if abs(moved.x()) < 4 and abs(moved.y()) < 4:
                    self._open_command_center()
            self.drag_start = None
            self.press_pos = None
            event.accept()

        def mouseDoubleClickEvent(self, event: Any) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self._open_command_center()

        def _show_menu(self, position: QPoint) -> None:
            menu = QMenu(self)
            menu.addAction(QAction("Open Command Center", self, triggered=self._open_command_center))
            menu.addAction(QAction("Open Project Folder", self, triggered=self._open_project_folder))
            menu.addAction(QAction("Open Logs", self, triggered=self._open_logs))
            menu.addAction(QAction("Refresh Status", self, triggered=self._refresh_status))
            roam = QAction("Roam Around Desktop", self)
            roam.setCheckable(True)
            roam.setChecked(self.roam_enabled)
            roam.triggered.connect(self._toggle_roam)
            menu.addAction(roam)
            menu.addAction(QAction("Dock Top Right", self, triggered=self._dock_top_right))
            menu.addSeparator()
            menu.addAction(QAction("Quit Pet", self, triggered=QApplication.instance().quit))
            menu.exec(position)

        def _open_command_center(self) -> None:
            if sys.platform == "win32" and self._focus_dashboard_window():
                return
            target = args.dashboard_url or args.backend
            QDesktopServices.openUrl(QUrl(target))

        def _focus_dashboard_window(self) -> bool:
            import json as _json
            import subprocess

            title = args.dashboard_title.replace("'", "''")
            script = f"""
$title = '{title}'
$sig = @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Win32FocusJarvis {{
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}}
'@
Add-Type $sig -ErrorAction SilentlyContinue
$focused = $false
[Win32FocusJarvis]::EnumWindows({{
  param($hWnd, $lParam)
  if ([Win32FocusJarvis]::IsWindowVisible($hWnd)) {{
    $builder = New-Object System.Text.StringBuilder 512
    [void][Win32FocusJarvis]::GetWindowText($hWnd, $builder, $builder.Capacity)
    if ($builder.ToString().Contains($title)) {{
      [void][Win32FocusJarvis]::SetForegroundWindow($hWnd)
      $script:focused = $true
      return $false
    }}
  }}
  return $true
}}, [IntPtr]::Zero) | Out-Null
@{{ focused = $focused }} | ConvertTo-Json -Compress
"""
            try:
                completed = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", script],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if completed.returncode != 0 or not completed.stdout.strip():
                    return False
                return bool(_json.loads(completed.stdout).get("focused"))
            except Exception:
                return False

        def _open_project_folder(self) -> None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT)))

        def _open_logs(self) -> None:
            logs = ROOT / "nexora_os" / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs)))

        def _toggle_roam(self) -> None:
            self.roam_enabled = not self.roam_enabled

        def _dock_top_right(self) -> None:
            screen = QApplication.primaryScreen()
            if screen is None:
                return
            bounds = screen.availableGeometry()
            self.roam_x = float(bounds.right() - self.width() - 24)
            self.roam_y = float(bounds.top() + 24)
            self.move(int(self.roam_x), int(self.roam_y))
            self.roam_enabled = False

        def closeEvent(self, event: Any) -> None:
            self.status_pool.shutdown(wait=False, cancel_futures=True)
            event.accept()

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

            bob = math.sin(self.phase) * 7
            pulse = 1.0 + (math.sin(self.phase * 2) * 0.025)
            cx, cy = 115, 119 + bob
            radius = 74 * pulse

            glow = QRadialGradient(cx, cy, radius * 1.6)
            glow.setColorAt(0.0, QColor(c1.red(), c1.green(), c1.blue(), 95))
            glow.setColorAt(0.55, QColor(c2.red(), c2.green(), c2.blue(), 48))
            glow.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - radius * 1.6, cy - radius * 1.6, radius * 3.2, radius * 3.2))

            shadow_width = 84 + math.sin(self.phase) * 8
            shadow = QRadialGradient(115, 226, 64)
            shadow.setColorAt(0.0, QColor(0, 0, 0, 62))
            shadow.setColorAt(0.75, QColor(0, 0, 0, 20))
            shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(shadow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(73 - shadow_width / 2 + 42, 217, shadow_width, 17))

            if self.robot_frames:
                frame_index = int((self.phase / math.tau) * len(self.robot_frames)) % len(self.robot_frames)
                if self.state.mode == "thinking":
                    frame_index = int((self.phase * 1.8 / math.tau) * len(self.robot_frames)) % len(self.robot_frames)
                robot = self.robot_frames[frame_index]
                x = int((self.width() - robot.width()) / 2 + math.sin(self.phase * 0.55) * 4)
                y = int(22 + bob)
                painter.drawPixmap(x, y, robot)
            else:
                painter.setBrush(c2)
                painter.setPen(QPen(c1, 3))
                painter.drawEllipse(QRectF(55, 35 + bob, 120, 120))

            painter.setPen(QPen(c1, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            scan_y = 72 + math.sin(self.phase * 2.2) * 8 + bob
            painter.drawLine(74, int(scan_y), 156, int(scan_y))
            if self.state.mode in {"thinking", "listening", "speaking"}:
                for i in range(3):
                    painter.drawEllipse(QRectF(44 + i * 64, 30 + math.sin(self.phase + i) * 4, 7, 7))

            panel = QRectF(18, 238, 194, 40)
            panel_path = QPainterPath()
            panel_path.addRoundedRect(panel, 8, 8)
            painter.setBrush(QColor(3, 7, 18, 205))
            painter.setPen(QPen(QColor(255, 255, 255, 55), 1))
            painter.drawPath(panel_path)

            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            painter.setPen(QColor(240, 249, 255))
            status = self.state.mode.upper()
            if self.roam_enabled:
                status += " / ROAM"
            painter.drawText(QRectF(24, 242, 182, 14), Qt.AlignmentFlag.AlignCenter, status)
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor(203, 213, 225))
            painter.drawText(QRectF(24, 257, 182, 14), Qt.AlignmentFlag.AlignCenter, self.state.message[:44])

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
                        "robot_asset": not pet.robot.isNull(),
                        "cached_frames": len(pet.robot_frames),
                        "roam_enabled": pet.roam_enabled,
                        "size": [pet.width(), pet.height()],
                    }
                )
            )
            app.exit(0)

        QTimer.singleShot(900, finish_smoke)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
