"""
JARVIS System Tray Manager & Background Service
===============================================
Provides:
  - Windows system tray icon with context menu
  - Single-instance enforcement (prevents duplicate JARVIS processes)
  - Windows startup registration (run JARVIS on boot)
  - System tray notifications (balloon tips)
  - Graceful shutdown + resource cleanup

Dependencies: PySide6 (included in main requirements)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("jarvis.tray")

ROOT     = Path(__file__).resolve().parent.parent
ICON_PATH = ROOT / "assets" / "jarvis_icon.png"   # Optional: fallback to text if missing


class TrayManager:
    """
    PySide6 system tray manager for JARVIS.
    Shows a persistent tray icon with quick actions.
    """

    def __init__(self, app, widget=None, dashboard=None, config: dict = None):
        self._app       = app
        self._widget    = widget
        self._dashboard = dashboard
        self._config    = config or {}
        self._tray      = None
        self._icon      = None
        self._setup_tray()

    def _setup_tray(self):
        from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
        from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont

        # ── Build icon (use file if available, else programmatic) ────────────
        if ICON_PATH.exists():
            pixmap = QPixmap(str(ICON_PATH))
        else:
            pixmap = self._make_icon()

        self._icon = QIcon(pixmap)

        # ── Tray ─────────────────────────────────────────────────────────────
        self._tray = QSystemTrayIcon(self._icon, self._app)
        self._tray.setToolTip("JARVIS AI — Active")

        # ── Context menu ──────────────────────────────────────────────────────
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #0f0708;
                color: #ffe9e6;
                border: 1px solid rgba(255,77,77,60);
                border-radius: 8px;
                font-family: 'Segoe UI';
                font-size: 13px;
                padding: 4px;
            }
            QMenu::item { padding: 6px 16px; }
            QMenu::item:selected { background: rgba(255,77,77,40); border-radius: 4px; }
            QMenu::separator { height: 1px; background: rgba(255,77,77,40); margin: 4px 8px; }
        """)

        if self._widget:
            act_widget = menu.addAction("⬡  Show Widget")
            act_widget.triggered.connect(lambda: (self._widget.show(), self._widget.raise_()))

        if self._dashboard:
            act_dash = menu.addAction("⊞  Open Dashboard")
            act_dash.triggered.connect(lambda: (self._dashboard.show(), self._dashboard.raise_()))

        menu.addSeparator()
        act_startup = menu.addAction("⚙  Configure Startup")
        act_startup.triggered.connect(self._open_startup_config)
        menu.addSeparator()

        act_quit = menu.addAction("✕  Quit JARVIS")
        act_quit.triggered.connect(self._quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()
        logger.info("System tray icon initialized")

    def _make_icon(self):
        """Generate a simple J icon if no PNG is available."""
        from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QRadialGradient
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)

        # Background circle
        from PySide6.QtGui import QRadialGradient
        from PySide6.QtCore import QRectF
        grad = QRadialGradient(16, 16, 16)
        grad.setColorAt(0.0, QColor(30, 8, 12))
        grad.setColorAt(1.0, QColor(10, 2, 5))
        p.setBrush(grad)
        from PySide6.QtGui import QPen
        from PySide6.QtCore import Qt
        p.setPen(QPen(QColor(255, 77, 77, 150), 1.5))
        p.drawEllipse(1, 1, 30, 30)

        # Letter J
        p.setPen(QColor(255, 77, 77))
        font = QFont("Courier New", 16, QFont.Bold)
        p.setFont(font)
        p.drawText(pixmap.rect(), Qt.AlignCenter, "J")
        p.end()
        return pixmap

    def _on_tray_activated(self, reason):
        from PySide6.QtWidgets import QSystemTrayIcon
        if reason == QSystemTrayIcon.Trigger:   # Left click
            if self._widget:
                if self._widget.isVisible():
                    self._widget.hide()
                else:
                    self._widget.show()
                    self._widget.raise_()

    def notify(self, title: str, message: str, duration_ms: int = 3000):
        """Show a balloon tip notification from the tray."""
        if self._tray and self._tray.isSystemTrayAvailable():
            from PySide6.QtWidgets import QSystemTrayIcon
            self._tray.showMessage(title, message,
                                   QSystemTrayIcon.Information, duration_ms)
            logger.debug(f"Tray notify: {title} — {message}")

    def _open_startup_config(self):
        """Open startup manager dialog."""
        try:
            mgr = StartupManager()
            enabled = mgr.is_registered()
            from PySide6.QtWidgets import QMessageBox, QPushButton
            msg = QMessageBox()
            msg.setWindowTitle("JARVIS Startup")
            msg.setText(
                f"JARVIS startup on boot is currently: {'ENABLED ✓' if enabled else 'DISABLED'}\n\n"
                f"{'Click Disable to remove from startup.' if enabled else 'Click Enable to start JARVIS on boot.'}"
            )
            btn_toggle = msg.addButton(
                "Disable" if enabled else "Enable",
                QMessageBox.AcceptRole
            )
            msg.addButton("Cancel", QMessageBox.RejectRole)
            msg.setStyleSheet("QMessageBox { color: #ffe9e6; background: #0f0708; }")
            msg.exec()
            if msg.clickedButton() == btn_toggle:
                if enabled:
                    mgr.unregister()
                    self.notify("JARVIS", "Removed from Windows startup.")
                else:
                    mgr.register()
                    self.notify("JARVIS", "Added to Windows startup.")
        except Exception as e:
            logger.warning(f"Startup config error: {e}")

    def _quit(self):
        logger.info("JARVIS shutdown initiated from tray.")
        if self._tray:
            self._tray.hide()
        self._app.quit()

    def hide(self):
        if self._tray:
            self._tray.hide()


class StartupManager:
    """
    Register/unregister JARVIS to run on Windows startup
    via the HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run registry key.
    """

    REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "JARVIS"

    def __init__(self):
        self._exe  = sys.executable
        self._script = str((ROOT / "jarvis_gui.py").resolve())
        self._cmd   = f'"{self._exe}" -X utf8 "{self._script}"'

    def is_registered(self) -> bool:
        """Check if JARVIS is in Windows startup registry."""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_KEY, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, self.APP_NAME)
            winreg.CloseKey(key)
            return bool(value)
        except (FileNotFoundError, OSError):
            return False
        except Exception as e:
            logger.warning(f"Registry read error: {e}")
            return False

    def register(self) -> dict:
        """Add JARVIS to Windows startup."""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_KEY, 0,
                                  winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, self.APP_NAME, 0, winreg.REG_SZ, self._cmd)
            winreg.CloseKey(key)
            logger.info(f"Startup registered: {self._cmd}")
            return {"ok": True, "cmd": self._cmd}
        except Exception as e:
            logger.error(f"Startup registration failed: {e}")
            return {"ok": False, "error": str(e)}

    def unregister(self) -> dict:
        """Remove JARVIS from Windows startup."""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_KEY, 0,
                                  winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, self.APP_NAME)
            winreg.CloseKey(key)
            logger.info("Startup unregistered")
            return {"ok": True}
        except Exception as e:
            logger.warning(f"Startup unregister error: {e}")
            return {"ok": False, "error": str(e)}


class SingleInstanceGuard:
    """
    Prevent multiple JARVIS instances using a lock file.
    """
    LOCK_FILE = ROOT / "logs" / "jarvis.lock"

    def __init__(self):
        self._lock_file = self.LOCK_FILE
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        self._acquired = False

    def acquire(self) -> bool:
        """Return True if this is the only JARVIS instance."""
        if self._lock_file.exists():
            try:
                pid = int(self._lock_file.read_text().strip())
                # Check if that PID is still alive
                import psutil
                if psutil.pid_exists(pid):
                    logger.warning(f"Another JARVIS instance found (PID {pid})")
                    return False
            except Exception:
                pass  # Lock file is stale — overwrite it
        # Write our PID
        self._lock_file.write_text(str(os.getpid()))
        self._acquired = True
        return True

    def release(self):
        if self._acquired:
            try:
                self._lock_file.unlink(missing_ok=True)
            except Exception:
                pass


__all__ = ["TrayManager", "StartupManager", "SingleInstanceGuard"]
