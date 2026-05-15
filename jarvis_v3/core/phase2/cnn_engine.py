"""
JARVIS Phase 2 — CNN Vision Engine
====================================
GPU-accelerated computer vision module using PyTorch and OpenCV.

Features:
  - Webcam capture (live frames)
  - Image classification (ResNet/MobileNet)
  - Object detection (YOLOv8 / torchvision)
  - Screen analysis
  - OCR preprocessing
  - Face detection
  - User presence detection
  - Dataset capture mode

Hardware target: RTX 4050 (CUDA), 16 GB RAM, Intel i5 14th Gen

Usage:
    from core.phase2.cnn_engine import CNNVisionEngine
    engine = CNNVisionEngine()
    result = await engine.classify_image("path/to/image.jpg")
    result = await engine.detect_objects_webcam()
    result = await engine.analyze_screen()
"""

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger("jarvis.phase2.cnn_engine")

# ─── Constants ─────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent.parent.parent
DATASETS    = ROOT / "datasets"
SCREENSHOTS = ROOT / "screenshots"
MODELS_DIR  = ROOT / "models"

for _d in [DATASETS, SCREENSHOTS, MODELS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ImageNet top-1000 label list (trimmed to first 20 for fallback display)
IMAGENET_CLASSES_FALLBACK = [
    "tench", "goldfish", "great_white_shark", "tiger_shark", "hammerhead",
    "electric_ray", "stingray", "cock", "hen", "ostrich",
    "brambling", "goldfinch", "house_finch", "junco", "indigo_bunting",
    "robin", "bulbul", "jay", "magpie", "chickadee"
]


# ─── GPU Detection ─────────────────────────────────────────────────────────────
def _get_device() -> tuple:
    """Returns (device_str, torch_ok). Catches OSError for broken CUDA DLLs."""
    try:
        import torch
        _ = torch.zeros(1)          # force DLL load NOW
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            logger.info(f"[CNN] Using GPU: {name}")
            return "cuda", True
        logger.info("[CNN] torch OK, CUDA not detected — using CPU")
        return "cpu", True
    except (ImportError, OSError) as e:
        logger.warning(f"[CNN] torch unavailable ({type(e).__name__}) — vision inference disabled")
        logger.warning("[CNN] Camera/face detection still work. Fix: launcher option [8] (reinstall PyTorch CUDA)")
    return "cpu", False


# ─── Image Preprocessing ───────────────────────────────────────────────────────
def _preprocess_image(path: str, size: Tuple[int, int] = (224, 224)):
    """Load and preprocess image. Returns None if torch/torchvision unavailable."""
    try:
        import torch
        from torchvision import transforms
        from PIL import Image

        transform = transforms.Compose([
            transforms.Resize(size),
            transforms.CenterCrop(size),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])
        img = Image.open(path).convert("RGB")
        tensor = transform(img).unsqueeze(0)  # add batch dim
        return tensor
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        return None


# ─── CNN Vision Engine ──────────────────────────────────────────────────────────
class CNNVisionEngine:
    """
    Central CNN vision module for JARVIS Phase 2.
    Handles all visual perception tasks via PyTorch.
    """

    def __init__(self, config: dict = None):
        self.config    = config or {}
        self.device, self._torch_ok = _get_device()   # _torch_ok=False if DLL broken
        self._model    = None          # classification model (lazy)
        self._yolo     = None          # object detection model (lazy)
        self._cam      = None          # OpenCV VideoCapture
        self._cam_lock = threading.Lock()
        self._running  = False

        # Dataset capture state
        self._capture_label    = None
        self._capture_count    = 0
        self._capture_target   = 0
        self._capture_callback = None

        logger.info(f"[CNN] CNNVisionEngine initialized on device={self.device}")

    # ── Model Loading ──────────────────────────────────────────────────────────
    def _load_classifier(self, model_name: str = "mobilenet_v3_small"):
        """Lazy-load a torchvision classification model."""
        if not self._torch_ok:
            return None
        if self._model is not None:
            return self._model
        try:
            import torch
            import torchvision.models as models
            logger.info(f"[CNN] Loading classifier: {model_name}")
            if model_name == "resnet18":
                m = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
            elif model_name == "resnet50":
                m = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
            elif model_name == "mobilenet_v3_large":
                m = models.mobilenet_v3_large(weights=models.MobileNet_V3_Large_Weights.DEFAULT)
            else:
                m = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
            m.eval().to(self.device)
            self._model = m
            logger.info(f"[CNN] Classifier loaded on {self.device}")
            return m
        except (ImportError, OSError):
            logger.error("[CNN] torchvision unavailable (broken DLL)")
            self._torch_ok = False
            return None
        except Exception as e:
            logger.error(f"[CNN] Failed to load classifier: {e}")
            return None

    def _load_yolo(self):
        """Lazy-load YOLOv8 for object detection."""
        if self._yolo is not None:
            return self._yolo
        try:
            from ultralytics import YOLO
            model_path = MODELS_DIR / "yolov8n.pt"
            self._yolo = YOLO(str(model_path) if model_path.exists() else "yolov8n.pt")
            logger.info("[CNN] YOLOv8n loaded for object detection")
            return self._yolo
        except ImportError:
            logger.warning("[CNN] ultralytics not installed. Run: pip install ultralytics")
            return None

    def _get_imagenet_labels(self) -> List[str]:
        """Load ImageNet class labels."""
        label_file = MODELS_DIR / "imagenet_classes.json"
        if label_file.exists():
            try:
                with open(label_file) as f:
                    return json.load(f)
            except Exception:
                pass
        # Download on first use
        try:
            import urllib.request
            url = "https://raw.githubusercontent.com/anishathalye/imagenet-simple-labels/master/imagenet-simple-labels.json"
            with urllib.request.urlopen(url, timeout=5) as resp:
                labels = json.loads(resp.read().decode())
            with open(label_file, "w") as f:
                json.dump(labels, f)
            return labels
        except Exception:
            return IMAGENET_CLASSES_FALLBACK

    # ── Camera Management ──────────────────────────────────────────────────────
    def open_camera(self, camera_id: int = 0) -> bool:
        """Open webcam for streaming."""
        with self._cam_lock:
            if self._cam and self._cam.isOpened():
                return True
            try:
                import cv2
                cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)  # DirectShow for Windows
                cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_FPS, 30)
                if cap.isOpened():
                    self._cam = cap
                    logger.info(f"[CNN] Camera {camera_id} opened")
                    return True
                logger.warning(f"[CNN] Camera {camera_id} could not be opened")
                return False
            except ImportError:
                logger.error("[CNN] OpenCV not installed. Run: pip install opencv-python")
                return False

    def close_camera(self):
        """Release webcam."""
        with self._cam_lock:
            if self._cam:
                self._cam.release()
                self._cam = None
                logger.info("[CNN] Camera released")

    def read_frame(self) -> Optional[np.ndarray]:
        """Capture one frame from webcam. Returns BGR numpy array or None."""
        with self._cam_lock:
            if not self._cam or not self._cam.isOpened():
                return None
            ret, frame = self._cam.read()
            return frame if ret else None

    def capture_frame_to_file(self, camera_id: int = 0) -> Optional[Path]:
        """Capture a single frame and save to screenshots dir."""
        try:
            import cv2
            if not self.open_camera(camera_id):
                return None
            frame = self.read_frame()
            if frame is None:
                return None
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            dest = SCREENSHOTS / f"webcam_{ts}.jpg"
            cv2.imwrite(str(dest), frame)
            return dest
        except Exception as e:
            logger.error(f"[CNN] Frame capture error: {e}")
            return None

    # ── Classification ─────────────────────────────────────────────────────────
    async def classify_image(
        self,
        path: str,
        model_name: str = "mobilenet_v3_small",
        top_k: int = 5,
    ) -> Dict:
        """
        Classify an image using a pretrained CNN.
        Returns top-k predictions with labels and confidence scores.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._classify_sync, path, model_name, top_k
        )

    def _classify_sync(self, path: str, model_name: str, top_k: int) -> Dict:
        if not self._torch_ok:
            return {"error": "torch unavailable (broken DLL — reinstall PyTorch CUDA)",
                    "top_label": "unavailable", "confidence": 0.0, "predictions": []}
        try:
            import torch
            model = self._load_classifier(model_name)
            if model is None:
                return {"error": "Classifier not available", "predictions": []}
            tensor = _preprocess_image(path)
            if tensor is None:
                return {"error": f"Cannot preprocess: {path}", "predictions": []}
            tensor = tensor.to(self.device)
            labels = self._get_imagenet_labels()
            with torch.no_grad():
                outputs = model(tensor)
                probs   = torch.nn.functional.softmax(outputs[0], dim=0)
                top     = torch.topk(probs, min(top_k, len(labels)))
            results = []
            for prob, idx in zip(top.values.cpu().numpy(), top.indices.cpu().numpy()):
                label = labels[idx] if idx < len(labels) else f"class_{idx}"
                results.append({"label": label, "confidence": round(float(prob) * 100, 2), "class_id": int(idx)})
            return {
                "predictions": results,
                "top_label":   results[0]["label"] if results else "unknown",
                "confidence":  results[0]["confidence"] if results else 0.0,
                "model":       model_name,
                "device":      self.device,
            }
        except (ImportError, OSError) as e:
            self._torch_ok = False
            logger.error(f"[CNN] torch DLL error in classify: {e}")
            return {"error": "torch DLL broken", "predictions": []}
        except Exception as e:
            logger.error(f"[CNN] Classification error: {e}")
            return {"error": str(e), "predictions": []}

    # ── Object Detection ────────────────────────────────────────────────────────
    async def detect_objects(
        self,
        path: Optional[str] = None,
        confidence: float = 0.45,
        use_webcam: bool = False,
    ) -> Dict:
        """
        Detect objects using YOLOv8.
        If path is None and use_webcam=True, captures a webcam frame first.
        """
        if path is None and use_webcam:
            frame_path = self.capture_frame_to_file()
            path = str(frame_path) if frame_path else None

        if path is None:
            # Fallback: screenshot
            try:
                import pyautogui
                from PIL import Image
                ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest = SCREENSHOTS / f"screen_{ts}.png"
                pyautogui.screenshot().save(str(dest))
                path = str(dest)
            except Exception:
                return {"error": "No image source available"}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._detect_yolo_sync, path, confidence
        )

    def _detect_yolo_sync(self, path: str, conf: float) -> Dict:
        try:
            model = self._load_yolo()
            if model is None:
                return self._detect_torchvision_fallback(path, conf)

            device_arg = 0 if self.device == "cuda" else "cpu"
            results    = model(path, conf=conf, device=device_arg, verbose=False)
            detections = []
            for r in results:
                for box in r.boxes:
                    detections.append({
                        "label":  r.names[int(box.cls)],
                        "conf":   round(float(box.conf), 3),
                        "bbox":   [round(x, 1) for x in box.xyxy[0].tolist()],
                    })
            # Sort by confidence
            detections.sort(key=lambda x: x["conf"], reverse=True)
            unique_labels = list({d["label"] for d in detections})
            return {
                "detections": detections,
                "count":      len(detections),
                "objects":    unique_labels,
                "source":     path,
                "model":      "yolov8n",
                "device":     self.device,
            }
        except Exception as e:
            logger.error(f"[CNN] YOLO detection error: {e}")
            return {"error": str(e), "detections": []}

    def _detect_torchvision_fallback(self, path: str, conf: float) -> Dict:
        """Fallback: use torchvision Faster R-CNN for object detection."""
        try:
            import torch
            import torchvision.transforms.functional as F
            from torchvision.models.detection import (
                fasterrcnn_mobilenet_v3_large_fpn,
                FasterRCNN_MobileNet_V3_Large_FPN_Weights,
            )
            from PIL import Image

            COCO_NAMES = [
                "__background__", "person", "bicycle", "car", "motorcycle",
                "airplane", "bus", "train", "truck", "boat", "traffic light",
                "fire hydrant", "N/A", "stop sign", "parking meter", "bench",
                "bird", "cat", "dog", "horse", "sheep", "cow", "elephant",
                "bear", "zebra", "giraffe", "N/A", "backpack", "umbrella",
                "N/A", "N/A", "handbag", "tie", "suitcase", "frisbee",
                "skis", "snowboard", "sports ball", "kite", "baseball bat",
                "baseball glove", "skateboard", "surfboard", "tennis racket",
                "bottle", "N/A", "wine glass", "cup", "fork", "knife",
                "spoon", "bowl", "banana", "apple", "sandwich", "orange",
                "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
                "chair", "couch", "potted plant", "bed", "N/A", "dining table",
                "N/A", "N/A", "toilet", "N/A", "tv", "laptop", "mouse",
                "remote", "keyboard", "cell phone", "microwave", "oven",
                "toaster", "sink", "refrigerator", "N/A", "book", "clock",
                "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
            ]

            weights = FasterRCNN_MobileNet_V3_Large_FPN_Weights.DEFAULT
            model   = fasterrcnn_mobilenet_v3_large_fpn(weights=weights)
            model.eval().to(self.device)

            img    = Image.open(path).convert("RGB")
            tensor = F.to_tensor(img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                preds = model(tensor)[0]

            detections = []
            for box, label, score in zip(
                preds["boxes"].cpu().numpy(),
                preds["labels"].cpu().numpy(),
                preds["scores"].cpu().numpy(),
            ):
                if float(score) >= conf:
                    name = COCO_NAMES[label] if label < len(COCO_NAMES) else str(label)
                    if name != "N/A":
                        detections.append({
                            "label": name,
                            "conf":  round(float(score), 3),
                            "bbox":  [round(float(x), 1) for x in box],
                        })
            unique_labels = list({d["label"] for d in detections})
            return {
                "detections": detections,
                "count":      len(detections),
                "objects":    unique_labels,
                "source":     path,
                "model":      "fasterrcnn_mobilenet (fallback)",
                "device":     self.device,
            }
        except Exception as e:
            return {"error": f"Fallback detection failed: {e}", "detections": []}

    # ── Screen Analysis ─────────────────────────────────────────────────────────
    async def analyze_screen(self, classify: bool = True, detect: bool = True) -> Dict:
        """
        Capture screen and run classification + object detection.
        Returns combined scene understanding report.
        """
        try:
            import pyautogui
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = SCREENSHOTS / f"analyze_{ts}.png"
            pyautogui.screenshot().save(str(dest))
        except Exception as e:
            return {"error": f"Screenshot failed: {e}"}

        result: Dict = {"timestamp": datetime.now().isoformat(), "source": str(dest)}

        tasks = []
        if classify:
            tasks.append(("classification", self.classify_image(str(dest))))
        if detect:
            tasks.append(("objects", self.detect_objects(str(dest))))

        for key, coro in tasks:
            try:
                result[key] = await coro
            except Exception as e:
                result[key] = {"error": str(e)}

        # Build scene summary
        objects = result.get("objects", {}).get("objects", [])
        top_cls = result.get("classification", {}).get("top_label", "")
        conf    = result.get("classification", {}).get("confidence", 0)

        if objects:
            result["scene_summary"] = (
                f"Scene contains: {', '.join(objects[:5])}. "
                f"Classification: {top_cls} ({conf:.1f}% confidence)."
            )
        elif top_cls:
            result["scene_summary"] = f"Screen classified as: {top_cls} ({conf:.1f}% confidence)."
        else:
            result["scene_summary"] = "Unable to analyze screen content."

        return result

    # ── User Presence Detection ─────────────────────────────────────────────────
    async def detect_user_presence(self, camera_id: int = 0) -> Dict:
        """
        Detect if a person (user) is in front of the camera.
        Returns presence status and face count.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._presence_sync, camera_id
        )

    def _presence_sync(self, camera_id: int) -> Dict:
        try:
            import cv2
            frame_path = self.capture_frame_to_file(camera_id)
            if not frame_path:
                return {"present": False, "faces": 0, "error": "Camera unavailable"}

            img  = cv2.imread(str(frame_path))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(cascade_path)
            faces   = cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
            )
            face_count = len(faces)

            return {
                "present":  face_count > 0,
                "faces":    face_count,
                "method":   "opencv_haar",
                "image":    str(frame_path),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"[CNN] Presence detection error: {e}")
            return {"present": False, "faces": 0, "error": str(e)}

    # ── Dataset Capture Mode ────────────────────────────────────────────────────
    async def start_dataset_capture(
        self,
        label: str,
        count: int = 50,
        interval_ms: int = 300,
        camera_id: int = 0,
        callback=None,
    ) -> Dict:
        """
        Capture a labeled image dataset from webcam.
        Saves images to datasets/<label>/webcam_NNNN.jpg

        Args:
            label:       Dataset class name
            count:       Number of images to capture
            interval_ms: Milliseconds between captures
            camera_id:   Camera index
            callback:    Optional callable(progress, total) for UI updates
        """
        label_dir = DATASETS / label
        label_dir.mkdir(parents=True, exist_ok=True)

        if not self.open_camera(camera_id):
            return {"error": "Cannot open camera"}

        captured = 0
        try:
            import cv2
            while captured < count:
                frame = self.read_frame()
                if frame is None:
                    await asyncio.sleep(0.1)
                    continue

                existing = len(list(label_dir.glob("*.jpg")))
                dest     = label_dir / f"img_{existing:05d}.jpg"
                cv2.imwrite(str(dest), frame)
                captured += 1

                if callback:
                    try:
                        callback(captured, count)
                    except Exception:
                        pass

                await asyncio.sleep(interval_ms / 1000.0)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[CNN] Dataset capture error: {e}")
            return {"error": str(e), "captured": captured}

        total_in_class = len(list(label_dir.glob("*.jpg")))
        return {
            "label":         label,
            "captured":      captured,
            "total_in_class": total_in_class,
            "directory":     str(label_dir),
        }

    # ── Active Application Vision ───────────────────────────────────────────────
    async def identify_active_application(self) -> Dict:
        """
        Identify what application is active on screen by combining
        window title (psutil) and screen visual classification.
        """
        result = {"method": "combined"}
        # Window title approach
        try:
            import subprocess, json as _json, sys
            if sys.platform == "win32":
                out = subprocess.run(
                    ["powershell", "-Command",
                     "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} "
                     "| Select-Object -First 5 Name,MainWindowTitle "
                     "| ConvertTo-Json"],
                    capture_output=True, text=True, timeout=6,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                data = _json.loads(out.stdout.strip() or "[]")
                if isinstance(data, dict):
                    data = [data]
                result["windows"] = data[:5]
                if data:
                    result["active_app"] = data[0].get("Name", "unknown")
                    result["active_title"] = data[0].get("MainWindowTitle", "")
        except Exception as e:
            result["window_error"] = str(e)

        # Screen visual classification
        try:
            cls = await self.classify_image(
                str(SCREENSHOTS / f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                if False else
                self._quick_screenshot_path()
            )
            result["visual_context"] = cls.get("top_label", "")
        except Exception:
            pass

        return result

    def _quick_screenshot_path(self) -> str:
        try:
            import pyautogui
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = SCREENSHOTS / f"quick_{ts}.png"
            pyautogui.screenshot().save(str(dest))
            return str(dest)
        except Exception:
            return ""

    # ── Custom Model Inference ──────────────────────────────────────────────────
    async def classify_with_custom_model(
        self,
        image_path: str,
        model_path: str,
        class_names: List[str],
        num_classes: int,
    ) -> Dict:
        """
        Run inference with a locally saved custom CNN checkpoint.

        Args:
            image_path:  Path to image
            model_path:  Path to .pth checkpoint saved by VisionTrainer
            class_names: List of class name strings
            num_classes: Number of output classes (must match checkpoint)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._custom_infer_sync, image_path, model_path, class_names, num_classes
        )

    def _custom_infer_sync(
        self, image_path: str, model_path: str, class_names: List[str], num_classes: int
    ) -> Dict:
        try:
            import torch
            import torchvision.models as models

            ckpt = torch.load(model_path, map_location=self.device)
            arch = ckpt.get("arch", "mobilenet_v3_small")

            if arch == "resnet18":
                m = models.resnet18(weights=None)
                m.fc = torch.nn.Linear(m.fc.in_features, num_classes)
            elif arch == "resnet50":
                m = models.resnet50(weights=None)
                m.fc = torch.nn.Linear(m.fc.in_features, num_classes)
            else:
                m = models.mobilenet_v3_small(weights=None)
                m.classifier[-1] = torch.nn.Linear(
                    m.classifier[-1].in_features, num_classes
                )

            m.load_state_dict(ckpt["model_state"])
            m.eval().to(self.device)

            tensor = _preprocess_image(image_path)
            if tensor is None:
                return {"error": "Image preprocessing failed"}

            tensor = tensor.to(self.device)
            with torch.no_grad():
                out   = m(tensor)
                probs = torch.nn.functional.softmax(out[0], dim=0)
                top   = torch.topk(probs, min(5, num_classes))

            results = []
            for prob, idx in zip(top.values.cpu().numpy(), top.indices.cpu().numpy()):
                name = class_names[idx] if idx < len(class_names) else f"class_{idx}"
                results.append({"label": name, "confidence": round(float(prob) * 100, 2)})

            return {
                "predictions":  results,
                "top_label":    results[0]["label"],
                "confidence":   results[0]["confidence"],
                "model_path":   model_path,
                "arch":         arch,
            }
        except Exception as e:
            logger.error(f"[CNN] Custom model inference failed: {e}")
            return {"error": str(e)}

    # ── Cleanup ─────────────────────────────────────────────────────────────────
    def shutdown(self):
        """Release all resources."""
        self.close_camera()
        self._model = None
        self._yolo  = None
        logger.info("[CNN] CNNVisionEngine shut down")


# ─── Quick test ─────────────────────────────────────────────────────────────────
async def _self_test():
    engine = CNNVisionEngine()
    print(f"Device: {engine.device}")

    # Presence test
    print("Testing user presence detection...")
    presence = await engine.detect_user_presence()
    print(f"  Presence: {presence}")

    # Screen analysis
    print("Analyzing screen...")
    analysis = await engine.analyze_screen()
    print(f"  Scene: {analysis.get('scene_summary', 'N/A')}")

    engine.shutdown()
    print("CNN Engine self-test complete.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_self_test())
