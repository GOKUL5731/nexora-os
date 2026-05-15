"""
JARVIS Floating Widget
Always-on-top glassmorphism HUD widget.
Mic button, quick chat, speaking animation, system stats.
PySide6 — no external dependencies beyond PyQt6/PySide6.
"""

import asyncio
import logging
import sys
import threading
from pathlib import Path

from PySide6.QtCore import (Qt, QTimer, QThread, Signal, QPropertyAnimation,
                             QEasingCurve, QRect, QPoint, QSize)
from PySide6.QtGui import (QFont, QColor, QPainter, QPen, QBrush, QLinearGradient,
                           QFontDatabase, QIcon, QPixmap, QRadialGradient, QPalette)
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                                QPushButton, QLabel, QLineEdit, QTextEdit,
                                QFrame, QSizeGrip, QGraphicsDropShadowEffect)

logger = logging.getLogger("jarvis.ui.widget")

# ── Color palette ─────────────────────────────────────────────────────────────
C_BG       = "#0a0e1a"
C_GLASS    = "rgba(28,8,10,205)"
C_ACCENT   = "#ff4d4d"
C_ACCENT2  = "#ff9966"
C_TEXT     = "#ffe9e6"
C_SUBTEXT  = "#d1a1a1"
C_SUCCESS  = "#ff7b5c"
C_WARN     = "#ffbf47"
C_BORDER   = "rgba(255,77,77,60)"


# ── Worker thread for async JARVIS calls ─────────────────────────────────────
class JarvisWorker(QThread):
    response_ready = Signal(str)
    error_occurred = Signal(str)
    thinking_start = Signal()
    thinking_stop  = Signal()

    def __init__(self, orchestrator, prompt: str):
        super().__init__()
        self.orchestrator = orchestrator
        self.prompt = prompt

    def run(self):
        self.thinking_start.emit()
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.orchestrator.process(self.prompt))
            loop.close()
            msg = result.get("message", "Done.")
            self.response_ready.emit(msg)
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.thinking_stop.emit()


class VoiceWorker(QThread):
    response_ready = Signal(str)
    error_occurred = Signal(str)
    listening_start = Signal()
    listening_stop = Signal()

    def __init__(self, voice_engine, orchestrator):
        super().__init__()
        self.voice_engine = voice_engine
        self.orchestrator = orchestrator

    def run(self):
        loop = None
        self.listening_start.emit()
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            heard = loop.run_until_complete(self.voice_engine.listen(timeout=10))
            text = heard.get("text", "").strip()
            if not text:
                raise RuntimeError(heard.get("error", "Didn't catch that. Please try again."))

            if not self.orchestrator:
                self.response_ready.emit(f'Heard: "{text}"')
                return

            result = loop.run_until_complete(
                self.orchestrator.process(text, context={"mode": "voice"})
            )
            msg = result.get("message", "Done.")
            self.response_ready.emit(f'Heard: "{text}"\n\n{msg}')
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.listening_stop.emit()
            if loop is not None:
                try:
                    loop.close()
                except Exception:
                    pass


# ── Animated orb (speaking indicator) ────────────────────────────────────────
class OrbWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 56)
        self._pulse = 0
        self._active = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_active(self, active: bool):
        self._active = active

    def _tick(self):
        if self._active:
            self._pulse = (self._pulse + 4) % 360
        else:
            self._pulse = (self._pulse + 1) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() // 2, self.height() // 2

        import math
        # Outer glow rings
        for i in range(3):
            r = 20 + i * 5
            alpha = 60 - i * 15
            if self._active:
                pulse_r = r + int(6 * abs(math.sin(math.radians(self._pulse + i * 30))))
                color = QColor(255, 77, 77, alpha)
            else:
                pulse_r = r
                color = QColor(255, 153, 102, alpha // 2)
            pen = QPen(color, 1.5)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(cx - pulse_r, cy - pulse_r, pulse_r * 2, pulse_r * 2)

        # Core orb
        grad = QRadialGradient(cx, cy, 14)
        if self._active:
            grad.setColorAt(0, QColor(255, 240, 235, 255))
            grad.setColorAt(0.5, QColor(255, 77, 77, 220))
            grad.setColorAt(1, QColor(140, 22, 22, 110))
        else:
            grad.setColorAt(0, QColor(255, 210, 190, 200))
            grad.setColorAt(0.5, QColor(255, 120, 80, 160))
            grad.setColorAt(1, QColor(90, 18, 18, 100))

        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx - 14, cy - 14, 28, 28)


# ── Glass panel base ──────────────────────────────────────────────────────────
class GlassPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C_GLASS};
                border: 1px solid {C_BORDER};
                border-radius: 16px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(255, 77, 77, 70))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)


# ── Main Widget ───────────────────────────────────────────────────────────────
class JARVISWidget(QWidget):
    def __init__(self, orchestrator=None, config: dict = None, voice_engine=None):
        super().__init__()
        self.orchestrator = orchestrator
        self.config = config or {}
        self.voice_engine = voice_engine
        self._drag_pos = None
        self._worker = None
        self._voice_worker = None
        self._is_listening = False

        self._setup_window()
        self._build_ui()
        self._start_stats_timer()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(360, 220)
        self.resize(380, 260)

        # Position: bottom-right corner
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 400, screen.height() - 310)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        panel = GlassPanel(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # ── Header ────────────────────────────────────────────────────────
        header = QHBoxLayout()
        orb_label = QLabel("⬡")
        orb_label.setStyleSheet(f"color: {C_ACCENT}; font-size: 18px;")
        title = QLabel("J A R V I S")
        title.setStyleSheet(f"""
            color: {C_ACCENT};
            font-family: 'Courier New', monospace;
            font-size: 14px;
            font-weight: bold;
            letter-spacing: 4px;
        """)
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {C_SUCCESS}; font-size: 10px;")
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,60,60,30);
                color: {C_SUBTEXT};
                border: none;
                border-radius: 11px;
                font-size: 10px;
            }}
            QPushButton:hover {{ background: rgba(255,60,60,120); color: white; }}
        """)
        self._close_btn.clicked.connect(self.hide)

        self._dashboard_btn = QPushButton("⊞")
        self._dashboard_btn.setFixedSize(22, 22)
        self._dashboard_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,77,77,18);
                color: {C_ACCENT};
                border: none;
                border-radius: 11px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: rgba(255,77,77,42); }}
        """)

        header.addWidget(orb_label)
        header.addSpacing(6)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._status_dot)
        header.addSpacing(4)
        header.addWidget(self._dashboard_btn)
        header.addSpacing(4)
        header.addWidget(self._close_btn)
        layout.addLayout(header)

        # ── Separator ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"border: none; border-top: 1px solid {C_BORDER};")
        layout.addWidget(sep)

        # ── Response area ──────────────────────────────────────────────────
        self._response = QLabel("Online. How can I assist, Sir?")
        self._response.setWordWrap(True)
        self._response.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._response.setMinimumHeight(70)
        self._response.setStyleSheet(f"""
            color: {C_TEXT};
            font-size: 13px;
            font-family: 'Segoe UI', sans-serif;
            line-height: 1.5;
            padding: 4px 0;
        """)
        layout.addWidget(self._response)

        # ── Orb + input row ────────────────────────────────────────────────
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._orb = OrbWidget()
        input_row.addWidget(self._orb)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask JARVIS anything…")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,77,77,10);
                border: 1px solid {C_BORDER};
                border-radius: 10px;
                color: {C_TEXT};
                font-size: 13px;
                padding: 8px 12px;
                font-family: 'Segoe UI', sans-serif;
            }}
            QLineEdit:focus {{
                border: 1px solid {C_ACCENT};
                background: rgba(255,77,77,18);
            }}
        """)
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input)

        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setFixedSize(38, 38)
        self._mic_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,77,77,20);
                border: 1px solid {C_BORDER};
                border-radius: 19px;
                font-size: 16px;
            }}
            QPushButton:hover {{ background: rgba(255,77,77,45); }}
            QPushButton:pressed {{ background: rgba(255,77,77,70); }}
        """)
        self._mic_btn.clicked.connect(self._toggle_mic)
        input_row.addWidget(self._mic_btn)

        layout.addLayout(input_row)

        # ── Quick stats bar ────────────────────────────────────────────────
        self._stats_bar = QLabel("CPU: --  RAM: --  Model: Ollama")
        self._stats_bar.setStyleSheet(f"""
            color: {C_SUBTEXT};
            font-size: 10px;
            font-family: 'Courier New', monospace;
            letter-spacing: 1px;
        """)
        layout.addWidget(self._stats_bar)

        root.addWidget(panel)

    # ── Interaction ───────────────────────────────────────────────────────────
    def _send(self):
        text = self._input.text().strip()
        if not text or not self.orchestrator:
            if not self.orchestrator:
                self._response.setText("⚠ Orchestrator not connected.")
            return
        self._input.clear()
        self._set_thinking(True)
        self._worker = JarvisWorker(self.orchestrator, text)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.thinking_stop.connect(lambda: self._set_thinking(False))
        self._worker.start()

    def _on_response(self, text: str):
        self._response.setText(text[:280] + ("…" if len(text) > 280 else ""))
        self._orb.set_active(False)
        self._status_dot.setStyleSheet(f"color: {C_SUCCESS}; font-size: 10px;")

    def _on_error(self, err: str):
        self._response.setText(f"⚠ {err[:120]}")
        self._status_dot.setStyleSheet(f"color: {C_WARN}; font-size: 10px;")

    def _set_thinking(self, thinking: bool):
        self._orb.set_active(thinking)
        if thinking:
            self._response.setText("Thinking…")
            self._status_dot.setStyleSheet(f"color: {C_ACCENT}; font-size: 10px;")

    def _toggle_mic(self):
        if self._is_listening:
            self._response.setText("🎤 Already listening…")
            return
        if not self.voice_engine:
            self._response.setText("🎤 Voice engine not available.")
            return

        self._voice_worker = VoiceWorker(self.voice_engine, self.orchestrator)
        self._voice_worker.listening_start.connect(self._on_listening_start)
        self._voice_worker.response_ready.connect(self._on_response)
        self._voice_worker.error_occurred.connect(self._on_error)
        self._voice_worker.listening_stop.connect(self._on_listening_stop)
        self._voice_worker.start()

    def _on_listening_start(self):
        self._is_listening = True
        self._orb.set_active(True)
        self._response.setText("Listening… speak now.")
        self._status_dot.setStyleSheet(f"color: {C_WARN}; font-size: 10px;")
        self._mic_btn.setText("◼")

    def _on_listening_stop(self):
        self._is_listening = False
        self._orb.set_active(False)
        self._mic_btn.setText("🎤")

    # ── Stats timer ───────────────────────────────────────────────────────────
    def _start_stats_timer(self):
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._update_stats)
        self._stats_timer.start(3000)

    def _update_stats(self):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            model = self.config.get("llm", {}).get("model", "?")
            provider = self.config.get("llm", {}).get("provider", "?")
            self._stats_bar.setText(
                f"CPU: {cpu:.0f}%  RAM: {ram:.0f}%  "
                f"Model: {model} ({provider})"
            )
        except Exception:
            self._stats_bar.setText("Stats unavailable (install psutil)")

    # ── Drag to move ──────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def set_dashboard_callback(self, fn):
        self._dashboard_btn.clicked.connect(fn)
