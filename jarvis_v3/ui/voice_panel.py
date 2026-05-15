import random
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QFrame
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QTimer, QRectF
from ui.theme import Theme
from ui.animations import Animations

class VoiceWaveWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.waveform_data = [0.2] * 40
        self.level = 0.0
        self.mode = "idle"
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_wave)
        self.timer.start(100)

    def update_wave(self):
        target = self.level if self.mode in {"listening", "speaking", "wake_listening"} else 0.05
        jitter = 0.18 if target > 0.08 else 0.03
        self.waveform_data = [
            max(0.03, min(1.0, val * 0.65 + target * 0.35 + random.uniform(-jitter, jitter)))
            for val in self.waveform_data
        ]
        self.update()

    def set_level(self, level: float):
        self.level = max(0.0, min(1.0, float(level)))

    def set_mode(self, mode: str):
        self.mode = mode or "idle"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center = self.rect().center()
        
        # Draw central circle
        radius = 40
        pen_circle = QPen(QColor(Theme.ACCENT_CYAN))
        pen_circle.setWidth(2)
        painter.setPen(pen_circle)
        painter.drawEllipse(center, radius, radius)
        
        # Draw outer circle (dashed)
        pen_dashed = QPen(QColor(Theme.ACCENT_CYAN_DIM))
        pen_dashed.setWidth(1)
        pen_dashed.setDashPattern([5, 5])
        painter.setPen(pen_dashed)
        painter.drawEllipse(center, radius + 10, radius + 10)
        
        # Draw Mic Icon (simplified)
        painter.setPen(QPen(QColor(Theme.TEXT_WHITE), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        mx, my = center.x(), center.y()
        painter.drawRoundedRect(mx - 4, my - 10, 8, 16, 4, 4)
        painter.drawLine(mx - 8, my + 2, mx - 8, my + 6)
        painter.drawLine(mx + 8, my + 2, mx + 8, my + 6)
        painter.drawArc(mx - 8, my - 2, 16, 16, 180 * 16, 180 * 16)
        painter.drawLine(mx, my + 14, mx, my + 18)
        painter.drawLine(mx - 4, my + 18, mx + 4, my + 18)

        # Draw waveform
        wave_width = self.width() - 40
        start_x = 20
        start_y = center.y()
        
        pen_wave = QPen(QColor(Theme.ACCENT_CYAN))
        pen_wave.setWidth(2)
        pen_wave.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_wave)
        
        num_bars = len(self.waveform_data)
        bar_spacing = wave_width / num_bars
        
        for i, val in enumerate(self.waveform_data):
            x = start_x + i * bar_spacing
            # Skip drawing where the circle is
            if abs(x - center.x()) < radius + 20:
                continue
                
            h = 40 * val
            painter.drawLine(x, start_y - h/2, x, start_y + h/2)


class VoicePanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "Panel")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header = QHBoxLayout()
        title1 = QLabel("JARVIS")
        title1.setFont(Theme.get_font(10, bold=True))
        title1.setStyleSheet(f"color: {Theme.TEXT_WHITE};")
        
        title2 = QLabel("VOICE INTERFACE")
        title2.setFont(Theme.get_font(10, bold=True))
        title2.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        
        header.addWidget(title1)
        header.addStretch()
        header.addWidget(title2)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Wave Widget
        self.wave = VoiceWaveWidget()
        layout.addWidget(self.wave)
        
        # Footer
        footer = QHBoxLayout()
        
        self.status = QLabel("Listening...")
        self.status.setFont(Theme.get_font(10))
        self.status.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        
        footer.addWidget(self.status)
        footer.addStretch()
        
        info_layout = QVBoxLayout()
        
        ww_label = QLabel("WAKE WORD")
        ww_label.setFont(Theme.get_font(8))
        ww_label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        ww_val = QLabel("JARVIS")
        ww_val.setFont(Theme.get_font(12, bold=True))
        ww_val.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        
        mode_label = QLabel("MODE")
        mode_label.setFont(Theme.get_font(8))
        mode_label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        mode_val = QLabel("VOICE")
        mode_val.setFont(Theme.get_font(12, bold=True))
        mode_val.setStyleSheet(f"color: {Theme.ACCENT_CYAN};")
        
        info_layout.addWidget(ww_label)
        info_layout.addWidget(ww_val)
        info_layout.addSpacing(10)
        info_layout.addWidget(mode_label)
        info_layout.addWidget(mode_val)
        
        footer.addLayout(info_layout)
        layout.addLayout(footer)

    def update_voice_state(self, state: dict, audio: dict = None):
        audio = audio or {}
        status = state.get("status", "idle")
        self.wave.set_mode(status)
        self.wave.set_level(audio.get("level", 0.0))
        label = {
            "idle": "Idle",
            "listening": "Listening...",
            "wake_listening": "Wake word armed",
            "wake_detected": "Wake word detected",
            "transcribing": "Transcribing...",
            "speaking": "Speaking...",
            "error": "Voice error",
            "stopped": "Stopped",
        }.get(status, status.replace("_", " ").title())
        self.status.setText(label)
        color = Theme.ACCENT_CYAN if status not in {"error", "stopped"} else Theme.TEXT_MUTED
        self.status.setStyleSheet(f"color: {color};")
