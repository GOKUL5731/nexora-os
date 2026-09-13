from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pyautogui
import pytesseract
from PIL import Image
import mss

try:
    from ultralytics import YOLO
except ImportError:  # Optional: object detection is disabled without this package.
    YOLO = None

from ..core.event_bus import EventBus
from ..core.cache import Cache

# Try to import QR code library
try:
    from cv2 import QRCodeDetector
    QR_CODE_AVAILABLE = True
except ImportError:
    QR_CODE_AVAILABLE = False


class VisionEngine:
    def __init__(self, captures: Path, bus: EventBus) -> None:
        self.captures = captures
        self.captures.mkdir(parents=True, exist_ok=True)
        self.bus = bus
        self.camera = None
        self.last_result: dict[str, Any] = {}
        self.gesture_control_enabled = False
        self.gesture_state = {"pan_x": 0, "pan_y": 0, "zoom": 1.0, "last_gesture": None}
        self.hands_detector = None
        self.mouse_control_enabled = False
        self.mouse_state = {"x": 0, "y": 0, "click": False, "scroll": 0}
        self.object_model = None
        self.object_model_error = ""
        self.object_model_path = self._find_object_model()
        self.continuous_running = False
        self.continuous_task = None
        self.last_objects: list[dict[str, Any]] = []
        self.last_object_scan_at = 0.0
        
        # QR code detector
        self.qr_detector = QRCodeDetector() if QR_CODE_AVAILABLE else None

    def _find_object_model(self) -> Path | None:
        configured = os.environ.get("NEXORA_YOLO_MODEL", "").strip()
        candidates = []
        if configured:
            candidates.append(Path(configured))
        package_root = Path(__file__).resolve().parents[2]
        repo_root = Path(__file__).resolve().parents[3]
        candidates.extend([
            package_root / "models" / "yolov8n.pt",
            repo_root / "models" / "yolov8n.pt",
        ])
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    async def start(self) -> dict[str, Any]:
        result = await asyncio.to_thread(self._start)
        if result.get("ok") and not self.continuous_running:
            self.continuous_running = True
            self.continuous_task = asyncio.create_task(self._continuous_loop())
        return result

    def _start(self) -> dict[str, Any]:
        try:
            if self.camera is None:
                camera, frame, backend_name, index = self._open_camera()
                if camera is None or frame is None:
                    result = {"ok": False, "error": "Camera initialized but failed to read frame", "webcam": "unavailable"}
                else:
                    self.camera = camera
                    result = {
                        "ok": True,
                        "webcam": "running",
                        "backend": backend_name,
                        "camera_index": index,
                        "width": int(frame.shape[1]),
                        "height": int(frame.shape[0]),
                    }
            else:
                ok = bool(self.camera and self.camera.isOpened())
                result = {"ok": ok, "webcam": "running" if ok else "unavailable"}
        except Exception as exc:
            result = {"ok": False, "error": str(exc), "webcam": "unavailable"}
        self._sync(result)
        return result

    def _open_camera(self) -> tuple[Any | None, Any | None, str, int]:
        backends = [
            ("DirectShow", getattr(cv2, "CAP_DSHOW", 0)),
            ("MSMF", getattr(cv2, "CAP_MSMF", 0)),
            ("Default", getattr(cv2, "CAP_ANY", 0)),
        ]
        for index in range(4):
            for backend_name, backend in backends:
                camera = cv2.VideoCapture(index, backend)
                if not camera or not camera.isOpened():
                    if camera:
                        camera.release()
                    continue
                camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                frame = None
                for _ in range(8):
                    ok, candidate = camera.read()
                    if ok and candidate is not None:
                        frame = candidate
                        break
                    time.sleep(0.08)
                if frame is not None:
                    return camera, frame, backend_name, index
                camera.release()
        return None, None, "", -1

    async def stop(self) -> dict[str, Any]:
        self.continuous_running = False
        if self.continuous_task:
            self.continuous_task.cancel()
            self.continuous_task = None
        if self.camera is not None:
            await asyncio.to_thread(self.camera.release)
            self.camera = None
        result = {"ok": True, "webcam": "stopped"}
        self._sync(result)
        return result

    async def _continuous_loop(self):
        while self.continuous_running:
            try:
                await asyncio.to_thread(self._capture_latest)
            except Exception as e:
                pass
            await asyncio.sleep(2.0)  # analyze every 2 seconds

    def _capture_latest(self) -> None:
        if not self.camera or not self.camera.isOpened():
            return
        ok, frame = self.camera.read()
        if not ok:
            return
        path = self.captures / "latest.jpg"
        cv2.imwrite(str(path), frame)
        # We only do object detection in the background to save CPU, OCR is on-demand
        objects = self._objects(frame)
        faces = self._faces(frame)
        result = {
            "ok": True,
            "path": str(path),
            "width": int(frame.shape[1]),
            "height": int(frame.shape[0]),
            "faces": faces,
            "objects": objects,
            "timestamp": time.time()
        }
        self._sync(result)

    async def capture(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._capture)

    def _capture(self) -> dict[str, Any]:
        if self.camera is None:
            started = self._start()
            if not started.get("ok"):
                return started
        ok, frame = self.camera.read()
        if not ok:
            return {"ok": False, "error": "Webcam frame capture failed."}
        path = self.captures / f"webcam_{int(time.time())}.jpg"
        cv2.imwrite(str(path), frame)
        faces = self._faces(frame)
        objects = self._objects(frame)
        result = {"ok": True, "path": str(path), "width": int(frame.shape[1]), "height": int(frame.shape[0]), "faces": faces, "objects": objects}
        self._sync(result)
        return result

    async def screen(self, ocr: bool = True) -> dict[str, Any]:
        return await asyncio.to_thread(self._screen, ocr)

    def _screen(self, ocr: bool) -> dict[str, Any]:
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # primary monitor
                sct_img = sct.grab(monitor)
                # Convert to PIL Image for Tesseract
                image = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            path = self.captures / f"screen_{int(time.time())}.png"
            image.save(path)
            text = self._ocr(image) if ocr else ""
            result = {"ok": True, "path": str(path), "width": image.width, "height": image.height, "ocr_text": text}
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        self._sync(result)
        return result

    def _faces(self, frame: Any) -> list[dict[str, int]]:
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            return [{"x": int(x), "y": int(y), "width": int(w), "height": int(h)} for x, y, w, h in detector.detectMultiScale(gray, 1.1, 4)]
        except Exception:
            return []

    def _objects(self, frame: Any) -> list[dict[str, Any]]:
        try:
            model_path = self.object_model_path or self._find_object_model()
            self.object_model_path = model_path
            if not model_path:
                self.object_model_error = "YOLO model not found"
                return []
            if YOLO is None:
                self.object_model_error = "ultralytics package not installed"
                return []
            if self.object_model is None:
                self.object_model = YOLO(str(model_path))
            result = self.object_model.predict(frame, verbose=False)[0]
            self.object_model_error = ""
            return [{"label": result.names[int(box.cls[0])], "confidence": round(float(box.conf[0]), 3)} for box in result.boxes[:20]]
        except Exception as exc:
            self.object_model_error = str(exc)
            return []

    def _ocr(self, image: Any) -> str:
        try:
            # Configure Tesseract path for Windows
            tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if Path(tesseract_path).exists():
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            return pytesseract.image_to_string(image, lang="eng+tam").strip()
        except Exception:
            return ""

    def health(self) -> dict[str, Any]:
        return {
            "status": "online",
            "webcam": "running" if self.camera is not None else "stopped",
            "last_result": self.last_result,
            "object_detection": {
                "available": self.object_model_path is not None and YOLO is not None,
                "model_path": str(self.object_model_path) if self.object_model_path else "",
                "error": self.object_model_error,
            },
        }

    def _sync(self, result: dict[str, Any]) -> None:
        self.last_result = result
        self.bus.set_state("vision", self.health(), "vision_engine")
        self.bus.publish("vision.updated", result, "vision_engine")

    def _init_hands_detector(self) -> bool:
        try:
            # Use simple OpenCV-based gesture detection instead of MediaPipe
            # to avoid numpy compatibility issues
            import cv2
            self.hands_detector = "opencv_simple"  # Marker for simple detection
            return True
        except Exception:
            return False

    def _detect_gesture(self, frame: Any) -> dict[str, Any]:
        if not self.gesture_control_enabled or self.hands_detector is None:
            return {"gesture": None, "controls": {}}
        
        try:
            import cv2
            import numpy as np
            
            # Simple motion-based gesture detection
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Simple gesture detection based on motion patterns
            # This is a simplified approach to avoid MediaPipe dependency issues
            
            # Detect motion in different regions
            h, w = gray.shape
            regions = {
                "left": gray[:, :w//3],
                "center": gray[:, w//3:2*w//3],
                "right": gray[:, 2*w//3:]
            }
            
            # Calculate motion in each region (simplified)
            motion_scores = {}
            for region_name, region_img in regions.items():
                # Simple edge detection as motion proxy
                edges = cv2.Canny(region_img, 50, 150)
                motion_scores[region_name] = np.sum(edges) / (region_img.shape[0] * region_img.shape[1])
            
            # Determine gesture based on motion patterns
            gesture = None
            controls = {"pan_x": 0, "pan_y": 0, "zoom": 0}
            
            max_motion = max(motion_scores.values())
            
            if max_motion > 10:  # Threshold for significant motion
                if motion_scores["left"] > motion_scores["center"] and motion_scores["left"] > motion_scores["right"]:
                    gesture = "swipe_left"
                    controls["pan_x"] = -0.2
                elif motion_scores["right"] > motion_scores["center"] and motion_scores["right"] > motion_scores["left"]:
                    gesture = "swipe_right"
                    controls["pan_x"] = 0.2
                elif motion_scores["center"] > motion_scores["left"] and motion_scores["center"] > motion_scores["right"]:
                    gesture = "center_motion"
                    controls["zoom"] = 0.1
            
            # Smooth control updates
            if gesture:
                self.gesture_state["pan_x"] += controls["pan_x"] * 0.2
                self.gesture_state["pan_y"] += controls["pan_y"] * 0.2
                self.gesture_state["zoom"] += controls["zoom"] * 0.2
                
                # Clamp values
                self.gesture_state["pan_x"] = max(-1, min(1, self.gesture_state["pan_x"]))
                self.gesture_state["pan_y"] = max(-1, min(1, self.gesture_state["pan_y"]))
                self.gesture_state["zoom"] = max(0.5, min(3.0, self.gesture_state["zoom"]))
                
                self.gesture_state["last_gesture"] = gesture
            
            return {
                "gesture": gesture,
                "controls": {
                    "pan_x": round(self.gesture_state["pan_x"], 3),
                    "pan_y": round(self.gesture_state["pan_y"], 3),
                    "zoom": round(self.gesture_state["zoom"], 3)
                }
            }
        except Exception as e:
            return {"gesture": None, "controls": {}, "error": str(e)}

    async def enable_gesture_control(self) -> dict[str, Any]:
        result = await asyncio.to_thread(self._enable_gesture_control)
        return result

    def _enable_gesture_control(self) -> dict[str, Any]:
        if not self._init_hands_detector():
            return {"ok": False, "error": "Failed to initialize hands detector"}
        self.gesture_control_enabled = True
        return {"ok": True, "message": "Gesture control enabled"}

    async def disable_gesture_control(self) -> dict[str, Any]:
        self.gesture_control_enabled = False
        self.gesture_state = {"pan_x": 0, "pan_y": 0, "zoom": 1.0, "last_gesture": None}
        return {"ok": True, "message": "Gesture control disabled"}

    async def get_gesture_state(self) -> dict[str, Any]:
        return {
            "enabled": self.gesture_control_enabled,
            "state": self.gesture_state
        }

    async def capture_with_gestures(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._capture_with_gestures)

    def _capture_with_gestures(self) -> dict[str, Any]:
        if self.camera is None:
            started = self._start()
            if not started.get("ok"):
                return started
        
        ok, frame = self.camera.read()
        if not ok:
            return {"ok": False, "error": "Webcam frame capture failed."}
        
        import cv2
        import time
        
        # Detect gestures
        gesture_result = self._detect_gesture(frame)
        
        # Apply gesture controls to frame
        if gesture_result.get("controls"):
            controls = gesture_result["controls"]
            h, w = frame.shape[:2]
            
            # Apply pan
            pan_x = int(controls["pan_x"] * w * 0.3)
            pan_y = int(controls["pan_y"] * h * 0.3)
            
            # Apply zoom
            zoom = controls["zoom"]
            if zoom != 1.0:
                center_x, center_y = w // 2, h // 2
                new_w, new_h = int(w / zoom), int(h / zoom)
                x1 = max(0, center_x - new_w // 2 + pan_x)
                y1 = max(0, center_y - new_h // 2 + pan_y)
                x2 = min(w, center_x + new_w // 2 + pan_x)
                y2 = min(h, center_y + new_h // 2 + pan_y)
                
                if x2 > x1 and y2 > y1:
                    frame = frame[y1:y2, x1:x2]
                    frame = cv2.resize(frame, (w, h))
        
        # Save frame
        path = self.captures / f"webcam_gestures_{int(time.time())}.jpg"
        cv2.imwrite(str(path), frame)
        
        # Get other detections
        faces = self._faces(frame)
        objects = self._objects(frame)
        
        result = {
            "ok": True,
            "path": str(path),
            "width": int(frame.shape[1]),
            "height": int(frame.shape[0]),
            "faces": faces,
            "objects": objects,
            "gesture": gesture_result.get("gesture"),
            "controls": gesture_result.get("controls", {})
        }
        
        self._sync(result)
        return result

    async def get_frame(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_frame)

    def _get_frame(self) -> dict[str, Any]:
        if self.camera is None:
            started = self._start()
            if not started.get("ok"):
                return started
        
        ok, frame = self.camera.read()
        if not ok:
            return {"ok": False, "error": "Webcam frame capture failed."}
        
        faces = self._faces(frame)
        objects = self._objects_throttled(frame)
        gesture_result = self._detect_gesture(frame) if self.gesture_control_enabled else {"gesture": None, "controls": self.gesture_state}

        self._draw_overlays(frame, faces, objects, gesture_result)
        frame_base64 = self._encode_frame(frame)
        
        result = {
            "ok": True,
            "frame": frame_base64,
            "width": int(frame.shape[1]),
            "height": int(frame.shape[0]),
            "faces": faces,
            "objects": objects,
            "gesture": gesture_result.get("gesture"),
            "controls": gesture_result.get("controls", self.gesture_state),
            "gesture_control": self.gesture_control_enabled,
            "mouse_control": self.mouse_control_enabled,
            "mouse_state": self.mouse_state,
        }
        
        return result

    async def enable_mouse_control(self) -> dict[str, Any]:
        self.mouse_control_enabled = True
        return {"ok": True, "message": "Mouse control enabled"}

    async def disable_mouse_control(self) -> dict[str, Any]:
        self.mouse_control_enabled = False
        self.mouse_state = {"x": 0, "y": 0, "click": False, "scroll": 0}
        return {"ok": True, "message": "Mouse control disabled"}

    async def get_mouse_state(self) -> dict[str, Any]:
        return {
            "enabled": self.mouse_control_enabled,
            "state": self.mouse_state
        }

    def _move_mouse(self, x: int, y: int) -> bool:
        try:
            pyautogui.moveTo(x, y, duration=0.1)
            return True
        except Exception:
            return False

    def _click_mouse(self, button: str = "left") -> bool:
        try:
            pyautogui.click(button=button)
            return True
        except Exception:
            return False

    def _scroll_mouse(self, amount: int) -> bool:
        try:
            pyautogui.scroll(amount)
            return True
        except Exception:
            return False

    def _detect_hand_position(self, frame: Any) -> dict[str, Any]:
        try:
            # Simple motion detection to find hand position
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Use frame difference for motion detection
            if not hasattr(self, 'prev_frame'):
                self.prev_frame = gray
                return {"x": 0, "y": 0, "detected": False}
            
            diff = cv2.absdiff(self.prev_frame, gray)
            self.prev_frame = gray
            
            # Threshold and find contours
            _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Find the largest contour (likely the hand)
                largest_contour = max(contours, key=cv2.contourArea)
                if cv2.contourArea(largest_contour) > 1000:
                    x, y, w, h = cv2.boundingRect(largest_contour)
                    center_x = x + w // 2
                    center_y = y + h // 2
                    
                    # Map to screen coordinates
                    screen_width, screen_height = 1920, 1080  # Default screen resolution
                    frame_height, frame_width = gray.shape
                    
                    screen_x = int((center_x / frame_width) * screen_width)
                    screen_y = int((center_y / frame_height) * screen_height)
                    
                    return {
                        "x": screen_x,
                        "y": screen_y,
                        "detected": True,
                        "confidence": min(1.0, cv2.contourArea(largest_contour) / 10000)
                    }
            
            return {"x": 0, "y": 0, "detected": False}
        except Exception as e:
            return {"x": 0, "y": 0, "detected": False, "error": str(e)}

    def _detect_gesture_for_mouse(self, frame: Any) -> dict[str, Any]:
        if not self.mouse_control_enabled:
            return {"gesture": None, "action": None}
        
        try:
            
            # Detect hand position
            hand_pos = self._detect_hand_position(frame)
            
            if not hand_pos.get("detected"):
                return {"gesture": None, "action": None, "position": hand_pos}
            
            # Move mouse to hand position
            if self.mouse_control_enabled:
                self._move_mouse(hand_pos["x"], hand_pos["y"])
                self.mouse_state["x"] = hand_pos["x"]
                self.mouse_state["y"] = hand_pos["y"]
            
            # Detect gestures for clicks/scrolls
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape
            
            # Simple gesture detection based on motion patterns
            # This is a simplified approach - can be enhanced with MediaPipe later
            
            # Detect if hand is making a fist (click gesture)
            # Using motion density as a proxy
            motion_density = np.sum(gray) / (h * w)
            
            gesture = None
            action = None
            
            if motion_density > 80:  # Darker area (fist)
                gesture = "fist"
                action = "click"
                if not self.mouse_state["click"]:
                    self._click_mouse()
                    self.mouse_state["click"] = True
            elif motion_density < 60:  # Lighter area (open palm)
                gesture = "open_palm"
                action = "release"
                self.mouse_state["click"] = False
            
            return {
                "gesture": gesture,
                "action": action,
                "position": hand_pos,
                "mouse_state": self.mouse_state
            }
        except Exception as e:
            return {"gesture": None, "action": None, "error": str(e)}

    async def get_frame_with_mouse_control(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_frame_with_mouse_control)

    def _get_frame_with_mouse_control(self) -> dict[str, Any]:
        if self.camera is None:
            started = self._start()
            if not started.get("ok"):
                return started
        
        ok, frame = self.camera.read()
        if not ok:
            return {"ok": False, "error": "Webcam frame capture failed."}
        
        gesture_result = {"gesture": None, "action": None}
        if self.mouse_control_enabled:
            gesture_result = self._detect_gesture_for_mouse(frame)
            
            # Draw hand position on frame
            if gesture_result.get("position", {}).get("detected"):
                pos = gesture_result["position"]
                cv2.circle(frame, (int(pos["x"] * frame.shape[1] / 1920), int(pos["y"] * frame.shape[0] / 1080)), 10, (0, 255, 0), -1)

        faces = self._faces(frame)
        objects = self._objects_throttled(frame)
        scene_gesture = self._detect_gesture(frame) if self.gesture_control_enabled else {"gesture": None, "controls": self.gesture_state}
        self._draw_overlays(frame, faces, objects, scene_gesture)
        frame_base64 = self._encode_frame(frame)
        
        result = {
            "ok": True,
            "frame": frame_base64,
            "width": int(frame.shape[1]),
            "height": int(frame.shape[0]),
            "faces": faces,
            "objects": objects,
            "gesture": scene_gesture.get("gesture") or gesture_result.get("gesture"),
            "controls": scene_gesture.get("controls", self.gesture_state),
            "gesture_action": gesture_result.get("action"),
            "mouse_control": self.mouse_control_enabled,
            "mouse_state": self.mouse_state
        }
        
        return result

    def _objects_throttled(self, frame: Any, interval: float = 2.0) -> list[dict[str, Any]]:
        now = time.time()
        if now - self.last_object_scan_at < interval:
            return self.last_objects
        self.last_objects = self._objects(frame)
        self.last_object_scan_at = now
        return self.last_objects

    def _encode_frame(self, frame: Any) -> str:
        import base64
        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            return ""
        return base64.b64encode(buffer).decode("utf-8")

    def _draw_overlays(
        self,
        frame: Any,
        faces: list[dict[str, int]],
        objects: list[dict[str, Any]],
        gesture_result: dict[str, Any],
    ) -> None:
        for face in faces:
            x, y, w, h = face["x"], face["y"], face["width"], face["height"]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (6, 182, 212), 2)
            cv2.putText(frame, "face", (x, max(16, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (6, 182, 212), 1)

        y = 24
        for obj in objects[:5]:
            label = str(obj.get("label", "object"))
            confidence = obj.get("confidence", "")
            cv2.putText(frame, f"{label} {confidence}", (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 160), 2)
            y += 22

        gesture = gesture_result.get("gesture") or self.gesture_state.get("last_gesture")
        if gesture:
            cv2.putText(frame, f"gesture: {gesture}", (12, frame.shape[0] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 220, 80), 2)
