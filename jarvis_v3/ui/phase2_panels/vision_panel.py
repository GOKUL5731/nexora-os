"""
JARVIS Phase 2 — Vision Panel (PySide6)
=========================================
Live camera preview, object detection display, classification results.
Integrates with CNNVisionEngine.
"""

import asyncio
import logging
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QImage, QPixmap, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTextEdit, QProgressBar, QComboBox, QLineEdit,
    QScrollArea, QGridLayout, QGroupBox,
)

logger = logging.getLogger("jarvis.ui.vision_panel")

# ── Color constants (matching dashboard) ─────────────────────────────────────────
DARK   = "#0a0e1a"; PANEL  = "#0f1628"; CARD   = "#131d35"
ACCENT = "#00d4ff"; ACCENT2 = "#7b2fff"
TEXT   = "#e8f4ff"; MUTED  = "#4a6a8a"; BORDER = "#1a2a4a"
SUCCESS = "#00ff9d"; WARN   = "#ffaa00"; ERR   = "#ff4466"


def _card_style(color: str = BORDER) -> str:
    return f"background:{CARD};border:1px solid {color};border-radius:10px;padding:8px;"


# ── Camera Worker Thread ──────────────────────────────────────────────────────────
class CameraWorker(QThread):
    """Captures frames from webcam and emits QPixmap signals."""
    frame_ready = Signal(object)  # emits numpy array
    error       = Signal(str)

    def __init__(self, cnn_engine, camera_id: int = 0):
        super().__init__()
        self.cnn       = cnn_engine
        self.camera_id = camera_id
        self._running  = False

    def run(self):
        try:
            import cv2
            import numpy as np
            self._running = True
            if not self.cnn.open_camera(self.camera_id):
                self.error.emit("Cannot open camera")
                return
            while self._running:
                frame = self.cnn.read_frame()
                if frame is not None:
                    self.frame_ready.emit(frame)
                self.msleep(33)  # ~30 FPS
        except ImportError:
            self.error.emit("OpenCV not installed")
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._running = False
        self.wait(2000)


# ── Detection Worker ──────────────────────────────────────────────────────────────
class DetectionWorker(QThread):
    """Runs CNN detection/classification in background."""
    result_ready = Signal(dict)
    error        = Signal(str)

    def __init__(self, cnn_engine, task: str, image_path: str = ""):
        super().__init__()
        self.cnn        = cnn_engine
        self.task       = task
        self.image_path = image_path

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            if self.task == "classify":
                result = loop.run_until_complete(self.cnn.classify_image(self.image_path))
            elif self.task == "detect":
                result = loop.run_until_complete(self.cnn.detect_objects(self.image_path))
            elif self.task == "screen":
                result = loop.run_until_complete(self.cnn.analyze_screen())
            elif self.task == "presence":
                result = loop.run_until_complete(self.cnn.detect_user_presence())
            else:
                result = {"error": f"Unknown task: {self.task}"}
            loop.close()
            self.result_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ── Vision Panel ──────────────────────────────────────────────────────────────────
class VisionPanel(QWidget):
    """
    Main Vision Tab UI:
      - Live camera feed (MJPEG-style preview)
      - One-click object detection
      - Screen analysis
      - Classification results
      - User presence indicator
    """

    def __init__(self, cnn_engine=None, parent=None):
        super().__init__(parent)
        self.cnn          = cnn_engine
        self._cam_worker: CameraWorker = None
        self._det_worker: DetectionWorker = None
        self._last_frame  = None
        self._capture_count = 0
        self._dataset_label = ""
        self._build_ui()
        self._start_auto_refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(8, 8, 8, 8)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("👁  VISION ENGINE")
        title.setStyleSheet(f"color:{ACCENT};font-size:15px;font-weight:bold;letter-spacing:2px;")
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color:{MUTED};font-size:14px;")
        self._status_lbl = QLabel("Idle")
        self._status_lbl.setStyleSheet(f"color:{MUTED};font-size:11px;")
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self._status_dot)
        hdr.addWidget(self._status_lbl)
        root.addLayout(hdr)

        # ── Main 2-column layout ──────────────────────────────────────────────
        splitter = QHBoxLayout()
        splitter.setSpacing(10)

        # Left: Camera preview
        cam_frame = QFrame()
        cam_frame.setStyleSheet(_card_style(ACCENT))
        cam_lay = QVBoxLayout(cam_frame)

        cam_title = QLabel("📷 Live Camera")
        cam_title.setStyleSheet(f"color:{ACCENT};font-size:12px;font-weight:bold;")
        cam_lay.addWidget(cam_title)

        self._cam_label = QLabel()
        self._cam_label.setMinimumSize(320, 240)
        self._cam_label.setStyleSheet(
            f"background:#000;border:1px solid {BORDER};border-radius:6px;"
        )
        self._cam_label.setAlignment(Qt.AlignCenter)
        self._cam_label.setText("Camera Offline")
        self._cam_label.setStyleSheet(
            f"background:#050810;color:{MUTED};border:1px solid {BORDER};border-radius:6px;"
            f"font-size:12px;qproperty-alignment:AlignCenter;"
        )
        cam_lay.addWidget(self._cam_label, 1)

        # Camera controls
        cam_ctrl = QHBoxLayout()
        self._btn_cam_start = QPushButton("▶ Start Feed")
        self._btn_cam_stop  = QPushButton("■ Stop Feed")
        self._btn_snapshot  = QPushButton("📸 Snapshot")
        self._btn_presence  = QPushButton("👤 Presence")

        for btn in [self._btn_cam_start, self._btn_cam_stop,
                    self._btn_snapshot, self._btn_presence]:
            btn.setStyleSheet(
                f"QPushButton{{background:rgba(0,212,255,12);color:{ACCENT};"
                f"border:1px solid {BORDER};border-radius:6px;padding:5px 10px;font-size:11px;}}"
                f"QPushButton:hover{{background:rgba(0,212,255,30);border-color:{ACCENT};}}"
            )
            cam_ctrl.addWidget(btn)

        self._btn_cam_start.clicked.connect(self._start_camera)
        self._btn_cam_stop.clicked.connect(self._stop_camera)
        self._btn_snapshot.clicked.connect(self._take_snapshot)
        self._btn_presence.clicked.connect(self._detect_presence)
        self._btn_cam_stop.setEnabled(False)

        cam_lay.addLayout(cam_ctrl)

        # Dataset capture row
        ds_row = QHBoxLayout()
        self._ds_label_input = QLineEdit()
        self._ds_label_input.setPlaceholderText("Class label for capture...")
        self._ds_label_input.setStyleSheet(
            f"background:{CARD};border:1px solid {BORDER};border-radius:6px;"
            f"color:{TEXT};padding:4px;font-size:11px;"
        )
        self._btn_capture = QPushButton("📂 Capture Dataset")
        self._btn_capture.setStyleSheet(
            f"QPushButton{{background:rgba(123,47,255,20);color:{ACCENT2};"
            f"border:1px solid {ACCENT2};border-radius:6px;padding:5px 10px;font-size:11px;}}"
            f"QPushButton:hover{{background:rgba(123,47,255,40);}}"
        )
        self._btn_capture.clicked.connect(self._start_dataset_capture)
        ds_row.addWidget(self._ds_label_input, 1)
        ds_row.addWidget(self._btn_capture)
        cam_lay.addLayout(ds_row)

        self._capture_progress = QProgressBar()
        self._capture_progress.setRange(0, 100)
        self._capture_progress.setValue(0)
        self._capture_progress.setVisible(False)
        self._capture_progress.setStyleSheet(
            f"QProgressBar{{background:{CARD};border:1px solid {BORDER};border-radius:4px;"
            f"color:{TEXT};font-size:10px;}}"
            f"QProgressBar::chunk{{background:{ACCENT2};border-radius:3px;}}"
        )
        cam_lay.addWidget(self._capture_progress)

        splitter.addWidget(cam_frame, 1)

        # Right: Detection results
        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        # Analysis controls
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet(_card_style())
        ctrl_lay = QVBoxLayout(ctrl_frame)
        ctrl_title = QLabel("🔍 Analysis")
        ctrl_title.setStyleSheet(f"color:{ACCENT};font-size:12px;font-weight:bold;")
        ctrl_lay.addWidget(ctrl_title)

        btn_row1 = QHBoxLayout()
        self._btn_screen   = QPushButton("🖥  Analyze Screen")
        self._btn_classify = QPushButton("🏷  Classify Image")
        self._btn_detect   = QPushButton("🎯 Detect Objects")

        for btn in [self._btn_screen, self._btn_classify, self._btn_detect]:
            btn.setStyleSheet(
                f"QPushButton{{background:rgba(0,212,255,12);color:{ACCENT};"
                f"border:1px solid {BORDER};border-radius:6px;padding:6px 10px;font-size:11px;}}"
                f"QPushButton:hover{{background:rgba(0,212,255,30);border-color:{ACCENT};}}"
            )
            btn_row1.addWidget(btn)

        self._btn_screen.clicked.connect(lambda: self._run_detection("screen"))
        self._btn_classify.clicked.connect(lambda: self._run_detection("classify"))
        self._btn_detect.clicked.connect(lambda: self._run_detection("detect"))

        ctrl_lay.addLayout(btn_row1)
        right_col.addWidget(ctrl_frame)

        # Results panel
        res_frame = QFrame()
        res_frame.setStyleSheet(_card_style(SUCCESS))
        res_lay = QVBoxLayout(res_frame)
        res_title = QLabel("📊 Results")
        res_title.setStyleSheet(f"color:{SUCCESS};font-size:12px;font-weight:bold;")
        res_lay.addWidget(res_title)

        self._result_box = QTextEdit()
        self._result_box.setReadOnly(True)
        self._result_box.setStyleSheet(
            f"background:{DARK};border:none;color:{TEXT};"
            f"font-family:'Courier New';font-size:12px;"
        )
        self._result_box.setMinimumHeight(180)
        res_lay.addWidget(self._result_box, 1)
        right_col.addWidget(res_frame, 1)

        # Detections list
        det_frame = QFrame()
        det_frame.setStyleSheet(_card_style())
        det_lay = QVBoxLayout(det_frame)
        det_title = QLabel("🎯 Detected Objects")
        det_title.setStyleSheet(f"color:{WARN};font-size:12px;font-weight:bold;")
        det_lay.addWidget(det_title)
        self._det_list = QTextEdit()
        self._det_list.setReadOnly(True)
        self._det_list.setStyleSheet(
            f"background:{DARK};border:none;color:{TEXT};"
            f"font-family:'Courier New';font-size:11px;"
        )
        self._det_list.setMaximumHeight(120)
        det_lay.addWidget(self._det_list)
        right_col.addWidget(det_frame)

        splitter.addLayout(right_col, 1)
        root.addLayout(splitter, 1)

        # ── Bottom bar ────────────────────────────────────────────────────────
        bot = QHBoxLayout()
        self._info_lbl = QLabel("CNN Engine ready")
        self._info_lbl.setStyleSheet(f"color:{MUTED};font-size:10px;")
        bot.addWidget(self._info_lbl)
        bot.addStretch()
        self._fps_lbl = QLabel("Camera: --")
        self._fps_lbl.setStyleSheet(f"color:{MUTED};font-size:10px;")
        bot.addWidget(self._fps_lbl)
        root.addLayout(bot)

    # ── Camera Control ─────────────────────────────────────────────────────────
    def _start_camera(self):
        if not self.cnn:
            self._set_status("No CNN engine", ERR)
            return
        self._cam_worker = CameraWorker(self.cnn, 0)
        self._cam_worker.frame_ready.connect(self._on_frame)
        self._cam_worker.error.connect(lambda e: self._set_status(f"Camera: {e}", ERR))
        self._cam_worker.start()
        self._btn_cam_start.setEnabled(False)
        self._btn_cam_stop.setEnabled(True)
        self._set_status("Camera streaming", SUCCESS)

    def _stop_camera(self):
        if self._cam_worker:
            self._cam_worker.stop()
            self._cam_worker = None
        self.cnn.close_camera()
        self._btn_cam_start.setEnabled(True)
        self._btn_cam_stop.setEnabled(False)
        self._cam_label.setText("Camera Offline")
        self._set_status("Camera stopped", MUTED)

    def _on_frame(self, frame):
        """Convert numpy BGR frame to QPixmap and display."""
        try:
            import cv2
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
            pix  = QPixmap.fromImage(qimg)
            scaled = pix.scaled(
                self._cam_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self._cam_label.setPixmap(scaled)
            self._last_frame = frame
        except Exception as e:
            logger.warning(f"Frame display error: {e}")

    def _take_snapshot(self):
        if not self.cnn:
            return
        t = threading.Thread(target=self._snapshot_sync, daemon=True)
        t.start()

    def _snapshot_sync(self):
        path = self.cnn.capture_frame_to_file()
        if path:
            self._result_box.append(f"📸 Snapshot saved: {path.name}")

    def _detect_presence(self):
        if not self.cnn:
            return
        self._run_detection("presence")

    # ── Detection ──────────────────────────────────────────────────────────────
    def _run_detection(self, task: str):
        if not self.cnn:
            self._set_status("No CNN engine loaded", ERR)
            return

        # Get snapshot path for classify/detect
        image_path = ""
        if task in ("classify", "detect") and self._last_frame is not None:
            try:
                import cv2
                from pathlib import Path
                ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest = Path("screenshots") / f"det_{ts}.jpg"
                dest.parent.mkdir(exist_ok=True)
                cv2.imwrite(str(dest), self._last_frame)
                image_path = str(dest)
            except Exception:
                pass

        self._set_status(f"Running {task}...", WARN)
        worker = DetectionWorker(self.cnn, task, image_path)
        worker.result_ready.connect(self._on_detection_result)
        worker.error.connect(lambda e: self._set_status(f"Error: {e}", ERR))
        worker.start()
        self._det_worker = worker

    def _on_detection_result(self, result: dict):
        if "error" in result:
            self._set_status(f"Error: {result['error']}", ERR)
            return

        self._set_status("Analysis complete", SUCCESS)

        # Format result for display
        lines = []
        if "scene_summary" in result:
            lines.append(f"Scene: {result['scene_summary']}")
        if "predictions" in result:
            for p in result["predictions"][:5]:
                lines.append(f"  {p['label']}: {p['confidence']:.1f}%")
        if "present" in result:
            status = "✓ Present" if result["present"] else "✗ Not detected"
            lines.append(f"User presence: {status} ({result.get('faces', 0)} face(s))")
        if "top_label" in result:
            lines.append(f"Top class: {result['top_label']} ({result.get('confidence', 0):.1f}%)")

        self._result_box.append("\n".join(lines))
        self._result_box.append("─" * 40)

        # Detections
        detections = result.get("detections", [])
        if detections:
            det_lines = []
            for d in detections[:10]:
                det_lines.append(
                    f"• {d['label']} [{d['conf']:.0%}]"
                )
            self._det_list.setPlainText("\n".join(det_lines))
        elif result.get("objects"):
            self._det_list.setPlainText(", ".join(result["objects"]))

    # ── Dataset Capture ────────────────────────────────────────────────────────
    def _start_dataset_capture(self):
        if not self.cnn:
            return
        label = self._ds_label_input.text().strip()
        if not label:
            self._result_box.append("⚠ Enter a class label first")
            return

        self._dataset_label = label
        self._capture_count = 0
        self._capture_progress.setVisible(True)
        self._capture_progress.setValue(0)
        self._btn_capture.setEnabled(False)

        count = 50

        def progress_cb(done, total):
            pct = int(done / total * 100)
            self._capture_progress.setValue(pct)
            self._fps_lbl.setText(f"Capturing: {done}/{total}")
            if done >= total:
                self._btn_capture.setEnabled(True)
                self._result_box.append(f"✓ Captured {total} images for '{label}'")
                self._capture_progress.setVisible(False)
                self._fps_lbl.setText("Capture complete")

        t = threading.Thread(
            target=self._capture_sync,
            args=(label, count, progress_cb),
            daemon=True,
        )
        t.start()

    def _capture_sync(self, label: str, count: int, cb):
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            self.cnn.start_dataset_capture(label=label, count=count, callback=cb)
        )
        loop.close()

    # ── Auto-refresh ───────────────────────────────────────────────────────────
    def _start_auto_refresh(self):
        timer = QTimer(self)
        timer.timeout.connect(self._refresh_info)
        timer.start(5000)

    def _refresh_info(self):
        if self._cam_worker and self._cam_worker.isRunning():
            self._fps_lbl.setText("Camera: Live ●")
        else:
            self._fps_lbl.setText("Camera: Offline")

    def _set_status(self, msg: str, color: str = MUTED):
        self._status_lbl.setText(msg)
        self._status_dot.setStyleSheet(f"color:{color};font-size:14px;")
        self._info_lbl.setText(msg)

    def cleanup(self):
        """Call on window close."""
        if self._cam_worker:
            self._cam_worker.stop()
        if self.cnn:
            self.cnn.close_camera()
