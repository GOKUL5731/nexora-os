"""
JARVIS Vision Module — GPU-accelerated screen understanding.
- Screenshot + OCR (easyocr with GPU)
- Object detection (YOLOv8 with CUDA)
- Face detection (OpenCV DNN or face_recognition)
- Screen region reading
- Window/app detection
"""

import asyncio
import logging
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.vision")
IS_WIN = sys.platform == "win32"


class VisionEngine:
    """Unified vision pipeline — GPU accelerated where possible."""

    def __init__(self, config: dict):
        self.config    = config
        self._ocr      = None   # easyocr.Reader (lazy)
        self._yolo     = None   # YOLO model (lazy)
        self.gpu       = config.get("vision", {}).get("gpu", True)
        self.ss_dir    = Path("screenshots")
        self.ss_dir.mkdir(exist_ok=True)

    # ── Screenshot ────────────────────────────────────────────────────────────
    def screenshot(self, region=None) -> Optional[Path]:
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = self.ss_dir / f"screen_{ts}.png"
        try:
            import pyautogui
            img = pyautogui.screenshot(region=region)
            img.save(str(dest))
            return dest
        except ImportError:
            pass
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(bbox=region)
            img.save(str(dest))
            return dest
        except ImportError:
            logger.error("Install: pip install pyautogui Pillow")
            return None

    # ── OCR ───────────────────────────────────────────────────────────────────
    def _get_ocr(self):
        if self._ocr:
            return self._ocr
        try:
            import easyocr
            logger.info("Loading easyocr (GPU=%s)...", self.gpu)
            self._ocr = easyocr.Reader(["en", "ta"], gpu=self.gpu)
            return self._ocr
        except ImportError:
            logger.warning("easyocr not installed: pip install easyocr")
            return None

    async def ocr_screen(self) -> dict:
        """OCR the entire screen."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._ocr_screen_sync)

    def _ocr_screen_sync(self) -> dict:
        img_path = self.screenshot()
        if not img_path:
            return {"error": "Screenshot failed"}
        return self._ocr_file(str(img_path))

    async def ocr_file(self, path: str) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._ocr_file, path)

    def _ocr_file(self, path: str) -> dict:
        # Try easyocr first (GPU, Tamil+English)
        reader = self._get_ocr()
        if reader:
            try:
                results = reader.readtext(path)
                text    = " ".join(r[1] for r in results if r[2] > 0.4)
                return {"text": text, "regions": len(results), "method": "easyocr"}
            except Exception as e:
                logger.warning(f"easyocr failed: {e}")

        # Fallback: pytesseract
        try:
            import pytesseract
            from PIL import Image
            text = pytesseract.image_to_string(Image.open(path), lang="eng+tam")
            return {"text": text.strip(), "method": "tesseract"}
        except ImportError:
            pass

        return {"error": "No OCR backend available. Install: pip install easyocr"}

    # ── Object Detection ──────────────────────────────────────────────────────
    def _get_yolo(self):
        if self._yolo:
            return self._yolo
        try:
            from ultralytics import YOLO
            logger.info("Loading YOLOv8n...")
            self._yolo = YOLO("yolov8n.pt")
            return self._yolo
        except ImportError:
            return None

    async def detect_objects(self, path: str = None, confidence: float = 0.5) -> dict:
        if not path:
            img = self.screenshot()
            path = str(img) if img else None
        if not path:
            return {"error": "No image"}
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._detect_sync, path, confidence)

    def _detect_sync(self, path: str, conf: float) -> dict:
        model = self._get_yolo()
        if not model:
            return {"error": "Install: pip install ultralytics"}
        try:
            results = model(path, conf=conf, device=0 if self.gpu else "cpu")
            detections = []
            for r in results:
                for box in r.boxes:
                    detections.append({
                        "label": r.names[int(box.cls)],
                        "conf":  round(float(box.conf), 2),
                        "box":   [round(x, 1) for x in box.xyxy[0].tolist()],
                    })
            return {"detections": detections, "count": len(detections)}
        except Exception as e:
            return {"error": str(e)}

    # ── Face Detection ────────────────────────────────────────────────────────
    async def detect_faces(self, path: str = None) -> dict:
        if not path:
            img = self.screenshot()
            path = str(img) if img else None
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._detect_faces_sync, path)

    def _detect_faces_sync(self, path: str) -> dict:
        # Try face_recognition (dlib based)
        try:
            import face_recognition
            import numpy as np
            from PIL import Image
            img    = face_recognition.load_image_file(path)
            locs   = face_recognition.face_locations(img)
            return {"faces": len(locs), "locations": locs, "method": "face_recognition"}
        except ImportError:
            pass

        # Fallback: OpenCV Haar cascade
        try:
            import cv2
            img  = cv2.imread(path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = cascade.detectMultiScale(gray, 1.1, 4)
            return {"faces": len(faces), "method": "opencv_haar"}
        except ImportError:
            return {"error": "Install: pip install opencv-python"}

    # ── Window/App Detection ──────────────────────────────────────────────────
    async def list_visible_windows(self) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._list_windows)

    def _list_windows(self) -> dict:
        if not IS_WIN:
            return {"error": "Windows only"}
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
                 "Select-Object Name,MainWindowTitle | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            import json
            data = json.loads(result.stdout or "[]")
            if isinstance(data, dict):
                data = [data]
            windows = [{"name": w.get("Name",""), "title": w.get("MainWindowTitle","")}
                       for w in data]
            return {"windows": windows, "count": len(windows)}
        except Exception as e:
            return {"error": str(e)}

    # ── Webcam capture ────────────────────────────────────────────────────────
    async def capture_webcam(self, camera: int = 0) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._webcam_sync, camera)

    def _webcam_sync(self, cam: int) -> dict:
        try:
            import cv2
            cap = cv2.VideoCapture(cam)
            if not cap.isOpened():
                return {"error": f"Cannot open camera {cam}"}
            ret, frame = cap.read()
            cap.release()
            if not ret:
                return {"error": "Capture failed"}
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = self.ss_dir / f"webcam_{ts}.jpg"
            cv2.imwrite(str(dest), frame)
            return {"saved": str(dest), "resolution": f"{frame.shape[1]}x{frame.shape[0]}"}
        except ImportError:
            return {"error": "Install: pip install opencv-python"}

    # ── Describe screenshot (LLM-based) ───────────────────────────────────────
    async def describe_screen(self, llm_client=None) -> dict:
        """OCR screen then ask LLM to describe what's visible."""
        ocr_result = await self.ocr_screen()
        text = ocr_result.get("text", "")
        if not text:
            return {"description": "Screen appears empty or could not be read."}
        if llm_client:
            desc = await llm_client.complete(
                f"Describe what the user is looking at based on this screen text:\n{text[:800]}\n\n"
                f"Be concise, 1-2 sentences.",
                system="You are JARVIS analyzing a user's screen."
            )
            return {"description": desc, "raw_text": text[:200]}
        return {"description": text[:300]}
