"""JARVIS Vision Agent — OCR, screenshot reading. Windows compatible."""
import asyncio, logging, sys
from pathlib import Path
from agents.agent_registry import BaseAgent

logger = logging.getLogger("jarvis.agents.vision")


class VisionAgent(BaseAgent):
    def supported_tools(self):
        return ["ocr_screen", "ocr_image", "detect_objects", "capture_webcam", "read_screen_region"]

    async def execute(self, tool, args):
        if tool == "ocr_screen":       return await self._ocr_screen(args)
        if tool == "ocr_image":        return await self._ocr_image(args)
        if tool == "detect_objects":   return await self._detect(args)
        if tool == "capture_webcam":   return await self._webcam(args)
        if tool == "read_screen_region": return await self._region(args)
        raise ValueError(f"VisionAgent: unknown '{tool}'")

    async def _ocr_screen(self, args):
        import tempfile, datetime
        loop = asyncio.get_event_loop()
        def _snap():
            try:
                import pyautogui
                img = pyautogui.screenshot()
            except ImportError:
                from PIL import ImageGrab
                img = ImageGrab.grab()
            tmp = Path(tempfile.gettempdir()) / f"jarvis_screen_{datetime.datetime.now().strftime('%H%M%S')}.png"
            img.save(str(tmp))
            return tmp
        tmp = await loop.run_in_executor(None, _snap)
        result = await self._ocr_image({"path": str(tmp)})
        tmp.unlink(missing_ok=True)
        return result

    async def _ocr_image(self, args):
        path = args.get("path", "")
        loop = asyncio.get_event_loop()
        def _ocr():
            try:
                import easyocr
                reader = easyocr.Reader(["en", "ta"], gpu=False)
                results = reader.readtext(path)
                text = " ".join(r[1] for r in results)
                return {"text": text, "regions": len(results), "method": "easyocr"}
            except ImportError:
                pass
            try:
                import pytesseract
                from PIL import Image
                text = pytesseract.image_to_string(Image.open(path), lang="eng+tam")
                return {"text": text.strip(), "method": "tesseract"}
            except ImportError:
                pass
            return {"error": "Install easyocr or pytesseract: pip install easyocr"}
        return await loop.run_in_executor(None, _ocr)

    async def _detect(self, args):
        path = args.get("path", "")
        loop = asyncio.get_event_loop()
        def _det():
            try:
                from ultralytics import YOLO
                model = YOLO("yolov8n.pt")
                results = model(path, conf=args.get("confidence", 0.5))
                detections = []
                for r in results:
                    for box in r.boxes:
                        detections.append({"label": r.names[int(box.cls)], "conf": float(box.conf)})
                return {"detections": detections}
            except ImportError:
                return {"error": "Install: pip install ultralytics"}
        return await loop.run_in_executor(None, _det)

    async def _webcam(self, args):
        loop = asyncio.get_event_loop()
        def _cap():
            try:
                import cv2, datetime
                cap = cv2.VideoCapture(args.get("camera_index", 0))
                ret, frame = cap.read()
                cap.release()
                if not ret:
                    return {"error": "Camera capture failed"}
                out = Path("screenshots") / f"webcam_{datetime.datetime.now().strftime('%H%M%S')}.jpg"
                out.parent.mkdir(exist_ok=True)
                cv2.imwrite(str(out), frame)
                return {"saved": str(out)}
            except ImportError:
                return {"error": "Install: pip install opencv-python"}
        return await loop.run_in_executor(None, _cap)

    async def _region(self, args):
        region = args.get("region")  # (left, top, width, height)
        import tempfile, datetime
        loop = asyncio.get_event_loop()
        def _snap():
            try:
                import pyautogui
                img = pyautogui.screenshot(region=tuple(region) if region else None)
            except ImportError:
                from PIL import ImageGrab
                img = ImageGrab.grab(bbox=tuple(region) if region else None)
            tmp = Path(tempfile.gettempdir()) / "jarvis_region.png"
            img.save(str(tmp))
            return str(tmp)
        tmp = await loop.run_in_executor(None, _snap)
        return await self._ocr_image({"path": tmp})
