import math
import random
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QPainter, QColor, QPen, QRadialGradient, QFont
from PySide6.QtCore import Qt, QTimer, QRectF
from ui.theme import Theme
from ui.animations import Animations

class AICoreWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        
        # Core state
        self.angle_outer = 0
        self.angle_inner = 0
        self.angle_particles = 0
        self.pulse_intensity = 0.0
        self.pulse_dir = 1
        self.is_listening = False
        self.waveform_data = [random.uniform(0.2, 0.8) for _ in range(30)]

        # Animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(1000 // 60) # 60 FPS
        
        # Audio simulation timer
        self.audio_timer = QTimer(self)
        self.audio_timer.timeout.connect(self.update_waveform)
        self.audio_timer.start(100)

        # Labels
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        # Spacer for the core
        layout.addSpacing(250)
        
        self.subtitle = QLabel("How can I help you, Gokul?")
        self.subtitle.setFont(Theme.get_font(12))
        self.subtitle.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        self.subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.subtitle)

    def update_animation(self):
        self.angle_outer = (self.angle_outer + 1) % 360
        self.angle_inner = (self.angle_inner - 2) % 360
        self.angle_particles = (self.angle_particles + 0.5) % 360
        
        # Pulse effect
        pulse_speed = 0.05 if self.is_listening else 0.02
        self.pulse_intensity += pulse_speed * self.pulse_dir
        if self.pulse_intensity > 1.0:
            self.pulse_intensity = 1.0
            self.pulse_dir = -1
        elif self.pulse_intensity < 0.0:
            self.pulse_intensity = 0.0
            self.pulse_dir = 1
            
        self.update()

    def update_waveform(self):
        # Simulate audio waveform
        if self.is_listening:
            self.waveform_data = [random.uniform(0.4, 1.0) for _ in range(30)]
        else:
            self.waveform_data = [max(0.1, val * 0.8 + random.uniform(-0.1, 0.1)) for val in self.waveform_data]

    def set_listening(self, listening: bool):
        self.is_listening = listening

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center = self.rect().center()
        # Offset center slightly up to make room for text
        center.setY(center.y() - 20)
        
        radius = min(self.width(), self.height()) / 3
        
        # 1. Background Glow
        glow_radius = radius * (1.2 + self.pulse_intensity * 0.2)
        gradient = QRadialGradient(center, glow_radius)
        base_color = QColor(Theme.ACCENT_CYAN)
        base_color.setAlphaF(0.15 + self.pulse_intensity * 0.1)
        gradient.setColorAt(0, base_color)
        gradient.setColorAt(1, QColor(0, 0, 0, 0))
        
        painter.fillRect(self.rect(), gradient)
        
        # 2. Outer Ring (dashed)
        painter.translate(center)
        painter.rotate(self.angle_outer)
        
        pen_outer = QPen(QColor(Theme.ACCENT_CYAN_DIM))
        pen_outer.setWidth(2)
        pen_outer.setDashPattern([10, 5, 2, 5])
        painter.setPen(pen_outer)
        painter.drawEllipse(QRectF(-radius, -radius, radius * 2, radius * 2))
        
        # 3. Middle Ring (solid, glowing)
        painter.rotate(-self.angle_outer) # Reset rotation
        painter.rotate(self.angle_inner)
        
        mid_radius = radius * 0.85
        pen_mid = QPen(QColor(Theme.ACCENT_CYAN))
        pen_mid.setWidth(3)
        painter.setPen(pen_mid)
        painter.drawEllipse(QRectF(-mid_radius, -mid_radius, mid_radius * 2, mid_radius * 2))
        
        # Draw some arcs on the middle ring
        pen_arc = QPen(QColor(Theme.TEXT_WHITE))
        pen_arc.setWidth(4)
        pen_arc.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_arc)
        painter.drawArc(QRectF(-mid_radius, -mid_radius, mid_radius * 2, mid_radius * 2), 0, 45 * 16)
        painter.drawArc(QRectF(-mid_radius, -mid_radius, mid_radius * 2, mid_radius * 2), 180 * 16, 45 * 16)

        painter.rotate(-self.angle_inner) # Reset rotation
        painter.translate(-center.x(), -center.y()) # Reset translation
        
        # 4. Text "JARVIS"
        painter.setFont(Theme.get_title_font(24))
        painter.setPen(QColor(Theme.TEXT_WHITE))
        text_rect = QRectF(center.x() - radius, center.y() - 30, radius * 2, 40)
        painter.drawText(text_rect, Qt.AlignCenter, "J A R V I S")
        
        # 5. Waveform
        wave_width = radius * 1.2
        wave_height = 30
        start_x = center.x() - wave_width / 2
        start_y = center.y() + 20
        
        pen_wave = QPen(QColor(Theme.ACCENT_CYAN))
        pen_wave.setWidth(2)
        pen_wave.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_wave)
        
        num_bars = len(self.waveform_data)
        bar_spacing = wave_width / num_bars
        
        for i, val in enumerate(self.waveform_data):
            x = start_x + i * bar_spacing
            h = wave_height * val * (1.0 + self.pulse_intensity * 0.5)
            # Make center bars taller
            dist_from_center = abs(i - num_bars / 2) / (num_bars / 2)
            h *= (1.0 - dist_from_center * 0.8)
            
            painter.drawLine(x, start_y - h/2, x, start_y + h/2)

        painter.end()
