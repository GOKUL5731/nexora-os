"""
JARVIS Animated 3D HUD — Pure PySide6 QPainter
Rotating rings, radar sweep, pulsing orb, voice waveform, data panels.
"""
import math, random, time
from dataclasses import dataclass, field
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                           QRadialGradient, QLinearGradient, QPainterPath,
                           QFontDatabase)
from PySide6.QtWidgets import QWidget, QApplication, QVBoxLayout

from ui.core_visual import CoreVisual
from ui.holo_renderer import Renderer
from ui.panels import AIStatusPanel, CornerHUD, MetricsPanel, TopHUDBar

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = QColor(0, 3, 12)
C1      = QColor(0, 255, 255)
C2      = QColor(0, 135, 255)
C3      = QColor(48, 255, 200)
CG      = QColor(0, 255, 140)
CW      = QColor(255, 200, 40)
CT      = QColor(224, 252, 255)


@dataclass
class HUDAnimState:
    time: float = 0.0
    energy: float = 1.0
    camera_offset: tuple[float, float] = (0.0, 0.0)
    ring_angles: list[float] = field(default_factory=lambda: [0.0] * 6)

    def breathe(self, amount: float = 1.0) -> float:
        return (math.sin(self.time * 1.15) * 0.5 + 0.5) * amount


class JarvisHUD(QWidget):
    def __init__(self, orchestrator=None, config=None):
        super().__init__()
        self.orchestrator = orchestrator
        self.config       = config or {}
        self._angle       = 0.0      # main ring rotation
        self._radar       = 0.0      # radar sweep angle
        self._pulse       = 0.0      # orb pulse phase
        self._scan_y      = 0        # scanline y
        self._wave        = [0.0] * 80   # voice waveform
        self._wave_active = False
        self._status      = "ONLINE"
        self._response    = "All systems operational, Sir."
        self._stats       = {"cpu": 0, "ram": 0, "gpu": 0}
        self._model       = self.config.get("llm",{}).get("model","llama3.2")
        self._particles   = [self._new_particle() for _ in range(40)]
        self._grid_offset = 0
        self._anim        = HUDAnimState()
        self._last_frame  = time.perf_counter()
        self._drag_panel  = None
        self._drag_last   = QPointF()

        # Chat input state
        self._input_text  = ""
        self._cursor_vis  = True
        self._worker      = None

        self._setup_window()
        self._holo_renderer = Renderer()
        self._core_visual = CoreVisual(self.width() or 1920, self.height() or 1080)
        self._metrics_panel = MetricsPanel(32, 88, 270, 320)
        self._ai_panel = AIStatusPanel(max(320, self.width() - 292), 88, 260, 310)
        self._top_hud = TopHUDBar(self.width() or 1920, self.height() or 1080)
        self._corner_hud = CornerHUD(self.width() or 1920, self.height() or 1080)
        self._layout_holographic_ui()

        # Master timer 30fps
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

        # Stats timer
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._update_stats)
        self._stats_timer.start(2000)

        # Cursor blink
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._blink)
        self._cursor_timer.start(500)

    def _setup_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.setFocusPolicy(Qt.StrongFocus)

    def _layout_holographic_ui(self):
        w = self.width() or 1920
        h = self.height() or 1080
        self._core_visual.resize(w, h)
        self._top_hud.resize(w, h)
        self._corner_hud.resize(w, h)
        self._metrics_panel.set_position(32, 88)
        self._ai_panel.set_position(max(330, w - self._ai_panel.w - 32), 88)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_core_visual"):
            self._layout_holographic_ui()

    # ── Particle system ───────────────────────────────────────────────────────
    def _new_particle(self):
        w = self.width() or 1920
        h = self.height() or 1080
        return {
            "x": random.uniform(0, w),
            "y": random.uniform(0, h),
            "vx": random.uniform(-0.3, 0.3),
            "vy": random.uniform(-0.6, -0.1),
            "alpha": random.uniform(0.2, 0.8),
            "size": random.uniform(1, 3),
        }

    # ── Tick ──────────────────────────────────────────────────────────────────
    def _tick(self):
        self._angle  = (self._angle  + 0.4) % 360
        self._radar  = (self._radar  + 1.2) % 360
        self._pulse  = (self._pulse  + 0.05) % (2 * math.pi)
        self._scan_y = (self._scan_y + 3) % (self.height() or 1080)
        self._grid_offset = (self._grid_offset + 0.5) % 40

        # Evolve waveform
        if self._wave_active:
            for i in range(len(self._wave)):
                self._wave[i] = math.sin(i * 0.3 + self._pulse * 4) * \
                                 random.uniform(0.5, 1.0) * 30
        else:
            self._wave = [w * 0.85 + random.uniform(-0.5, 0.5) for w in self._wave]

        # Particles
        w, h = self.width(), self.height()
        for p in self._particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if p["y"] < 0 or p["x"] < 0 or p["x"] > w:
                p.update(self._new_particle())

        now = time.perf_counter()
        dt = min(0.05, now - self._last_frame)
        self._last_frame = now
        self._anim.time += dt
        activity = 1.0 + (0.22 if self._wave_active else 0.0)
        self._anim.energy = 0.96 + math.sin(self._anim.time * 1.2) * 0.035 + (0.11 if self._wave_active else 0.0)
        self._anim.camera_offset = (
            math.sin(self._anim.time * 0.31) * 18.0,
            math.cos(self._anim.time * 0.27) * 12.0,
        )
        speeds = [42.0, -67.0, 88.0, -120.0, 155.0, -30.0]
        for i, speed in enumerate(speeds):
            self._anim.ring_angles[i] = (self._anim.ring_angles[i] + speed * dt * activity) % 360

        self._core_visual.set_speaking(self._wave_active, 0.95 if self._wave_active else 0.0)
        self._core_visual.update(dt, self._anim)
        self._metrics_panel.update(dt, self._anim)
        self._ai_panel.set_state("PROCESSING" if self._status == "THINKING" else self._status)
        self._ai_panel.set_voice(self._wave_active)
        self._ai_panel.update(dt, self._anim)

        self.update()

    def _blink(self):
        self._cursor_vis = not self._cursor_vis

    def _update_stats(self):
        try:
            import psutil
            self._stats["cpu"] = psutil.cpu_percent(interval=None)
            self._stats["ram"] = psutil.virtual_memory().percent
        except Exception:
            pass
        try:
            import pynvml
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._stats["gpu"] = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
        except Exception:
            self._stats["gpu"] = 0

    # ── Main paint ────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        w, h = self.width(), self.height()
        self._paint_holographic(p, w, h)

    def _paint_holographic(self, p, w, h):
        p.fillRect(0, 0, w, h, BG)
        self._core_visual.draw_starfield(p, self._anim)
        self._core_visual.draw_grid(p, self._anim)
        self._core_visual.draw_horizon(p, self._anim)
        self._core_visual.draw_core_glow(p, self._anim)
        self._core_visual.draw_rings(p, self._anim)
        self._core_visual.draw_orbitals(p, self._anim)
        self._core_visual.draw_inner_core(p, self._anim)

        self._top_hud.draw(p, self._anim)
        self._metrics_panel.draw(p, self._anim)
        self._ai_panel.draw(p, self._anim)
        self._draw_response_console(p, w, h)
        self._draw_input_bar(p, w, h)
        self._corner_hud.draw(p, self._anim)
        self._core_visual.draw_scan_lines(p, self._anim)
        self._core_visual.draw_vignette(p, self._anim)

    def _draw_response_console(self, p, w, h):
        width = min(860, max(420, w - 760))
        x = max(40, (w - width) / 2)
        y = max(360, h - 220)
        rect = QRectF(x, y, width, 130)
        self._holo_renderer.draw_panel_bg(p, rect, glow_alpha=45, energy=self._anim.energy)
        self._holo_renderer.draw_panel_corners(p, rect, size=14, energy=self._anim.energy)
        self._holo_renderer.draw_panel_header(p, rect, "COMMAND CONSOLE", energy=self._anim.energy)

        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QPen(CT, 1))
        words = self._response.split()
        line = ""
        lines = []
        for word in words:
            test = (line + " " + word).strip()
            if p.fontMetrics().horizontalAdvance(test) < rect.width() - 28:
                line = test
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        if not lines:
            lines = ["Awaiting command."]
        for i, text in enumerate(lines[:4]):
            p.drawText(QPointF(rect.left() + 14, rect.top() + 54 + i * 20), text)

    # ── Grid ──────────────────────────────────────────────────────────────────
    def _draw_grid(self, p, w, h):
        pen = QPen(QColor(0, 80, 160, 18), 1)
        p.setPen(pen)
        step = 40
        off  = int(self._grid_offset)
        for x in range(-step + off % step, w + step, step):
            p.drawLine(x, 0, x, h)
        for y in range(0, h + step, step):
            p.drawLine(0, y, w, y)

    # ── Scanline ──────────────────────────────────────────────────────────────
    def _draw_scanline(self, p, w, h):
        grad = QLinearGradient(0, self._scan_y - 20, 0, self._scan_y + 20)
        grad.setColorAt(0,   QColor(0, 212, 255, 0))
        grad.setColorAt(0.5, QColor(0, 212, 255, 12))
        grad.setColorAt(1,   QColor(0, 212, 255, 0))
        p.fillRect(0, self._scan_y - 20, w, 40, grad)

    # ── Particles ─────────────────────────────────────────────────────────────
    def _draw_particles(self, p):
        for pt in self._particles:
            c = QColor(0, 212, 255, int(pt["alpha"] * 120))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(c))
            p.drawEllipse(QPointF(pt["x"], pt["y"]), pt["size"], pt["size"])

    # ── Rings ─────────────────────────────────────────────────────────────────
    def _draw_rings(self, p, cx, cy):
        rings = [
            (320, 3, C1, 30,  1.0, 0),
            (280, 2, C2, 50,  0.8, 60),
            (240, 2, C3, 20,  0.6, 120),
            (200, 1, C1, 40,  0.5, 180),
            (160, 2, CG, 30,  0.4, 90),
            (400, 1, C2, 60,  0.3, 45),
            (450, 1, C1, 80,  0.2, 135),
        ]
        for radius, width, color, gap, alpha, phase in rings:
            c = QColor(color)
            c.setAlphaF(alpha)
            pen = QPen(c, width)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            angle = (self._angle + phase) % 360
            span  = 360 * 16 - gap * 16
            p.drawArc(
                QRectF(cx - radius, cy - radius, radius * 2, radius * 2),
                int(angle * 16), span
            )

        # Reverse-rotating inner ring
        c2 = QColor(C3); c2.setAlphaF(0.6)
        p.setPen(QPen(c2, 2))
        angle2 = (-self._angle * 1.5) % 360
        p.drawArc(QRectF(cx - 120, cy - 120, 240, 240), int(angle2 * 16), 270 * 16)

    # ── Radar sweep ───────────────────────────────────────────────────────────
    def _draw_radar(self, p, cx, cy):
        rad = 320
        # Fade trail
        for i in range(30):
            angle_deg = (self._radar - i * 4) % 360
            alpha     = int((30 - i) / 30 * 80)
            c = QColor(0, 212, 255, alpha)
            p.setPen(QPen(c, 1))
            a = math.radians(angle_deg)
            x = cx + rad * math.cos(a)
            y = cy + rad * math.sin(a)
            p.drawLine(QPointF(cx, cy), QPointF(x, y))

        # Sweep line
        p.setPen(QPen(QColor(0, 255, 200, 200), 2))
        a = math.radians(self._radar)
        p.drawLine(QPointF(cx, cy),
                   QPointF(cx + rad * math.cos(a), cy + rad * math.sin(a)))

        # Tick marks around radar
        p.setPen(QPen(QColor(0, 150, 200, 80), 1))
        for deg in range(0, 360, 15):
            a1 = math.radians(deg)
            r1, r2 = rad - 8, rad + 2
            p.drawLine(QPointF(cx + r1 * math.cos(a1), cy + r1 * math.sin(a1)),
                       QPointF(cx + r2 * math.cos(a1), cy + r2 * math.sin(a1)))

    # ── Central orb ───────────────────────────────────────────────────────────
    def _draw_orb(self, p, cx, cy):
        pulse = abs(math.sin(self._pulse))
        r     = int(50 + pulse * 12)

        # Outer glow layers
        for i in range(5):
            gr = int(r * (2.5 - i * 0.3))
            alpha = int(30 - i * 5)
            c = QColor(0, 212, 255, alpha)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(c))
            p.drawEllipse(QPointF(cx, cy), gr, gr)

        # Core gradient
        grad = QRadialGradient(cx, cy, r)
        if self._wave_active:
            grad.setColorAt(0, QColor(200, 255, 255, 255))
            grad.setColorAt(0.4, QColor(0, 212, 255, 220))
            grad.setColorAt(1, QColor(0, 60, 150, 0))
        else:
            grad.setColorAt(0, QColor(180, 160, 255, 230))
            grad.setColorAt(0.5, QColor(80, 40, 200, 180))
            grad.setColorAt(1, QColor(20, 10, 80, 0))

        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # J in center
        p.setPen(QPen(QColor(255, 255, 255, 200), 1))
        font = QFont("Courier New", 22, QFont.Bold)
        p.setFont(font)
        p.drawText(QRectF(cx - 15, cy - 15, 30, 30), Qt.AlignCenter, "J")

    # ── Crosshairs ────────────────────────────────────────────────────────────
    def _draw_cross_hairs(self, p, cx, cy):
        p.setPen(QPen(QColor(0, 212, 255, 60), 1))
        p.drawLine(cx - 480, cy, cx + 480, cy)
        p.drawLine(cx, cy - 480, cx, cy + 480)
        # Dashes every 40px
        p.setPen(QPen(QColor(0, 212, 255, 40), 1, Qt.DashLine))
        for r in range(80, 460, 80):
            p.drawEllipse(QPointF(cx, cy), r, r)

    # ── Data panels ───────────────────────────────────────────────────────────
    def _panel_bg(self, p, x, y, w, h):
        grad = QLinearGradient(x, y, x + w, y + h)
        grad.setColorAt(0, QColor(0, 20, 60, 180))
        grad.setColorAt(1, QColor(0, 8, 30, 150))
        p.fillRect(int(x), int(y), int(w), int(h), grad)
        p.setPen(QPen(QColor(0, 212, 255, 60), 1))
        p.drawRect(int(x), int(y), int(w), int(h))

    def _draw_data_panels(self, p, w, h, cx, cy):
        # ── Top-left: System Stats ──────────────────────────────
        px, py, pw, ph = 30, 30, 260, 200
        self._panel_bg(p, px, py, pw, ph)
        p.setPen(QPen(C1, 1)); p.setFont(QFont("Courier New", 10, QFont.Bold))
        p.drawText(px + 10, py + 22, "SYSTEM STATUS")
        p.setPen(QPen(QColor(0, 212, 255, 60), 1))
        p.drawLine(px + 10, py + 28, px + pw - 10, py + 28)

        stats = [
            ("CPU",  self._stats["cpu"],  C1),
            ("RAM",  self._stats["ram"],  C3),
            ("GPU",  self._stats["gpu"],  CG),
        ]
        for i, (label, val, color) in enumerate(stats):
            oy = py + 50 + i * 45
            p.setPen(QPen(QColor(150, 200, 255, 180), 1))
            p.setFont(QFont("Courier New", 9))
            p.drawText(px + 10, oy, f"{label}  {val:.0f}%")
            # Bar
            bar_w = int((pw - 20) * val / 100)
            c = QColor(color); c.setAlphaF(0.25)
            p.fillRect(px + 10, oy + 4, pw - 20, 8, c)
            c2 = QColor(color); c2.setAlphaF(0.8)
            p.fillRect(px + 10, oy + 4, bar_w, 8, c2)

        # ── Top-right: Model + Clock ─────────────────────────────
        px2 = w - 290; py2 = 30; pw2 = 260; ph2 = 160
        self._panel_bg(p, px2, py2, pw2, ph2)
        p.setPen(QPen(C1, 1)); p.setFont(QFont("Courier New", 10, QFont.Bold))
        p.drawText(px2 + 10, py2 + 22, "AI CORE")
        p.setPen(QPen(QColor(0, 212, 255, 60), 1))
        p.drawLine(px2 + 10, py2 + 28, px2 + pw2 - 10, py2 + 28)

        now = datetime.now()
        p.setPen(QPen(CT, 1)); p.setFont(QFont("Courier New", 18, QFont.Bold))
        p.drawText(px2 + 10, py2 + 62, now.strftime("%H:%M:%S"))
        p.setFont(QFont("Courier New", 9))
        p.drawText(px2 + 10, py2 + 82, now.strftime("%A  %d %b %Y"))
        p.setPen(QPen(QColor(0, 255, 140, 200), 1))
        p.setFont(QFont("Courier New", 9))
        p.drawText(px2 + 10, py2 + 104, f"MODEL  {self._model}")
        p.drawText(px2 + 10, py2 + 120, f"STATUS {self._status}")
        p.drawText(px2 + 10, py2 + 136, "ENGINE OLLAMA LOCAL")

        # ── Bottom-left: Tools ───────────────────────────────────
        px3 = 30; py3 = h - 200; pw3 = 240; ph3 = 160
        self._panel_bg(p, px3, py3, pw3, ph3)
        p.setPen(QPen(C1, 1)); p.setFont(QFont("Courier New", 10, QFont.Bold))
        p.drawText(px3 + 10, py3 + 22, "ACTIVE MODULES")
        p.setPen(QPen(QColor(0, 212, 255, 60), 1))
        p.drawLine(px3 + 10, py3 + 28, px3 + pw3 - 10, py3 + 28)
        modules = ["[ON] LLM ROUTER", "[ON] MEMORY DB",
                   "[ON] PLUGIN ENGINE", "[ON] SAFETY CORE",
                   "[ON] BENCHMARK", "[ON] SELF-LEARN"]
        p.setFont(QFont("Courier New", 8))
        for i, m in enumerate(modules):
            p.setPen(QPen(CG if "[ON]" in m else CW, 1))
            p.drawText(px3 + 10, py3 + 48 + i * 18, m)

        # ── Bottom-right: Response ───────────────────────────────
        px4 = w - 420; py4 = h - 200; pw4 = 390; ph4 = 160
        self._panel_bg(p, px4, py4, pw4, ph4)
        p.setPen(QPen(C1, 1)); p.setFont(QFont("Courier New", 10, QFont.Bold))
        p.drawText(px4 + 10, py4 + 22, "JARVIS RESPONSE")
        p.setPen(QPen(QColor(0, 212, 255, 60), 1))
        p.drawLine(px4 + 10, py4 + 28, px4 + pw4 - 10, py4 + 28)
        p.setPen(QPen(CT, 1)); p.setFont(QFont("Segoe UI", 9))
        # Word wrap response
        words = self._response.split()
        line = ""; lines = []
        for wd in words:
            test = (line + " " + wd).strip()
            if p.fontMetrics().horizontalAdvance(test) < pw4 - 20:
                line = test
            else:
                lines.append(line); line = wd
        if line: lines.append(line)
        for i, ln in enumerate(lines[:6]):
            p.drawText(px4 + 10, py4 + 46 + i * 18, ln)

    # ── Voice waveform ────────────────────────────────────────────────────────
    def _draw_waveform(self, p, w, h):
        base_y  = h // 2
        wave_w  = 400
        start_x = w // 2 - wave_w // 2
        step    = wave_w / len(self._wave)
        path    = QPainterPath()
        path.moveTo(start_x, base_y)
        for i, amp in enumerate(self._wave):
            x = start_x + i * step
            y = base_y + amp
            path.lineTo(x, y)
        pen = QPen(QColor(0, 212, 255, 160), 2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

    # ── Input bar ─────────────────────────────────────────────────────────────
    def _draw_input_bar(self, p, w, h):
        bw = 700; bh = 44; bx = w // 2 - bw // 2; by = h - 70
        # Panel
        grad = QLinearGradient(bx, by, bx + bw, by + bh)
        grad.setColorAt(0, QColor(0, 30, 80, 200))
        grad.setColorAt(1, QColor(0, 10, 40, 200))
        p.fillRect(bx, by, bw, bh, grad)
        p.setPen(QPen(QColor(0, 212, 255, 120), 1))
        p.drawRect(bx, by, bw, bh)
        # Prompt
        p.setPen(QPen(C1, 1)); p.setFont(QFont("Courier New", 11))
        p.drawText(bx + 14, by + 29, "> " + self._input_text + ("|" if self._cursor_vis else ""))

    # ── Corner decorations ────────────────────────────────────────────────────
    def _draw_corner_deco(self, p, w, h):
        size = 30
        p.setPen(QPen(C1, 2))
        corners = [(0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)]
        for cx2, cy2, sx, sy in corners:
            p.drawLine(cx2, cy2, cx2 + sx * size, cy2)
            p.drawLine(cx2, cy2, cx2, cy2 + sy * size)

    # ── Status arc text ───────────────────────────────────────────────────────
    def _draw_status_text(self, p, w, h, cx, cy):
        labels = ["VISION", "VOICE", "MEMORY", "CODER", "SAFETY", "PLUGINS"]
        r = 370
        p.setFont(QFont("Courier New", 8))
        for i, lbl in enumerate(labels):
            angle = math.radians(i * 60 + self._angle * 0.1)
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            p.setPen(QPen(QColor(0, 212, 255, 140), 1))
            p.drawText(QRectF(x - 30, y - 10, 60, 20), Qt.AlignCenter, lbl)

    # ── Input handling ────────────────────────────────────────────────────────
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Return:
            self._send()
        elif key == Qt.Key_Backspace:
            self._input_text = self._input_text[:-1]
        elif key == Qt.Key_Escape:
            self.close()
        else:
            ch = event.text()
            if ch.isprintable():
                self._input_text += ch

    def _send(self):
        text = self._input_text.strip()
        if not text or not self.orchestrator:
            if not self.orchestrator:
                self._response = "Orchestrator not connected."
            self._input_text = ""
            return
        self._input_text  = ""
        self._response    = "Processing..."
        self._status      = "THINKING"
        self._wave_active = True

        from ui.widget import JarvisWorker
        self._worker = JarvisWorker(self.orchestrator, text)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(lambda e: self._on_response(f"Error: {e}"))
        self._worker.start()

    def _on_response(self, text):
        self._response    = text[:300]
        self._status      = "ONLINE"
        self._wave_active = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position()
            for panel in (self._metrics_panel, self._ai_panel):
                if panel.hit_header(pos.x(), pos.y()):
                    self._drag_panel = panel
                    self._drag_last = QPointF(pos)
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self._drag_panel is not None:
            delta = pos - self._drag_last
            self._drag_panel.move_by(delta.x(), delta.y())
            self._drag_last = QPointF(pos)
            self.update()
            return
        for panel in (self._metrics_panel, self._ai_panel):
            if panel.contains(pos.x(), pos.y()):
                panel.on_hover()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_panel = None
        super().mouseReleaseEvent(event)

    # Close on double-click
    def mouseDoubleClickEvent(self, event):
        self.close()
