"""
JARVIS Deep Learning Training Engine — RTX 4050 GPU Edition
===========================================================
Full PyTorch training pipeline supporting:
  - Custom image classifier training on local datasets
  - Webcam-based real-time dataset capture with labeling
  - Transfer learning (ResNet / EfficientNet backbone)
  - Continuous learning: retrain on new labeled data
  - LLM-assisted hyperparameter suggestions + training script generation
  - Training progress to SQLite, logs, and dashboard

Hardware target: RTX 4050 (6 GB VRAM) | Python 3.10+ | PyTorch CUDA
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("jarvis.training")

ROOT       = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT / "datasets"
MODELS_DIR  = ROOT / "models" / "trained"
TRAIN_DB    = ROOT / "database" / "training.db"


# ─────────────────────────────────────────────────────────────────────────────
# Training record dataclass
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class TrainingRun:
    id: str
    model_name: str
    dataset: str
    epochs: int
    batch_size: int
    lr: float
    status: str = "pending"          # pending|training|done|failed
    best_acc: float = 0.0
    best_epoch: int = 0
    total_epochs_done: int = 0
    error: str = ""
    model_path: str = ""
    started: str = field(default_factory=lambda: datetime.now().isoformat())
    finished: str = ""
    log: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d.pop("log")
        return d


# ─────────────────────────────────────────────────────────────────────────────
# GPU / Torch check
# ─────────────────────────────────────────────────────────────────────────────
def _get_device():
    """Return best available torch device with logging."""
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            logger.info(f"Training device: {name} (CUDA)")
            return torch.device("cuda")
        logger.warning("CUDA unavailable — training on CPU (slow)")
        return torch.device("cpu")
    except ImportError:
        logger.error("PyTorch not installed. Run: python setup_gpu.py")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Training Engine
# ─────────────────────────────────────────────────────────────────────────────
class TrainingEngine:
    """
    Local deep learning model training on RTX 4050.
    Supports classification tasks with webcam dataset capture.
    """

    def __init__(self, config: dict, llm_router=None):
        self.config    = config
        self.router    = llm_router
        self._runs: dict[str, TrainingRun] = {}
        self._device   = None          # lazy-loaded

        DATASET_DIR.mkdir(parents=True, exist_ok=True)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        TRAIN_DB.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── DB ───────────────────────────────────────────────────────────────────
    def _init_db(self):
        with sqlite3.connect(TRAIN_DB) as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id           TEXT PRIMARY KEY,
                    model_name   TEXT,
                    dataset      TEXT,
                    epochs       INTEGER,
                    batch_size   INTEGER,
                    lr           REAL,
                    status       TEXT,
                    best_acc     REAL,
                    best_epoch   INTEGER,
                    total_done   INTEGER,
                    error        TEXT,
                    model_path   TEXT,
                    started      TEXT,
                    finished     TEXT
                );
                CREATE TABLE IF NOT EXISTS epoch_logs (
                    run_id   TEXT,
                    epoch    INTEGER,
                    loss     REAL,
                    acc      REAL,
                    val_loss REAL,
                    val_acc  REAL,
                    ts       TEXT
                );
                CREATE TABLE IF NOT EXISTS datasets (
                    name        TEXT PRIMARY KEY,
                    path        TEXT,
                    classes     TEXT,
                    num_images  INTEGER,
                    created_at  TEXT
                );
            """)

    def _save_run(self, run: TrainingRun):
        with sqlite3.connect(TRAIN_DB) as c:
            c.execute("""
                INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                run.id, run.model_name, run.dataset, run.epochs, run.batch_size,
                run.lr, run.status, run.best_acc, run.best_epoch,
                run.total_epochs_done, run.error, run.model_path,
                run.started, run.finished
            ))

    def _save_epoch(self, run_id: str, epoch: int, loss: float, acc: float,
                    val_loss: float, val_acc: float):
        with sqlite3.connect(TRAIN_DB) as c:
            c.execute("INSERT INTO epoch_logs VALUES (?,?,?,?,?,?,?)",
                      (run_id, epoch, loss, acc, val_loss, val_acc,
                       datetime.now().isoformat()))

    # ── Dataset management ────────────────────────────────────────────────────
    def list_datasets(self) -> list[dict]:
        """List all available training datasets."""
        datasets = []
        for d in DATASET_DIR.iterdir():
            if not d.is_dir():
                continue
            classes = [c.name for c in d.iterdir() if c.is_dir()]
            count   = sum(
                len(list(c.glob("*.jpg")) + list(c.glob("*.png")) + list(c.glob("*.jpeg")))
                for c in d.iterdir() if c.is_dir()
            )
            datasets.append({
                "name": d.name,
                "path": str(d),
                "classes": classes,
                "num_images": count,
                "num_classes": len(classes),
            })
        return datasets

    def create_dataset(self, name: str, classes: list[str]) -> dict:
        """Create a new dataset directory with class sub-folders."""
        ds_path = DATASET_DIR / name
        if ds_path.exists():
            return {"ok": False, "error": f"Dataset '{name}' already exists"}
        for cls in classes:
            (ds_path / cls).mkdir(parents=True, exist_ok=True)
        logger.info(f"Dataset created: {name} with classes {classes}")
        return {"ok": True, "path": str(ds_path), "classes": classes}

    # ── Webcam Dataset Capture ────────────────────────────────────────────────
    async def capture_webcam_dataset(
        self, dataset: str, label: str,
        count: int = 30, delay_s: float = 0.5,
        progress_cb: Callable[[int, int, str], None] | None = None
    ) -> dict:
        """
        Capture `count` webcam frames and store under datasets/<dataset>/<label>/.
        Uses OpenCV (GPU-accelerated if available).
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._capture_sync(dataset, label, count, delay_s, progress_cb)
        )

    def _capture_sync(self, dataset: str, label: str, count: int,
                      delay_s: float, progress_cb) -> dict:
        try:
            import cv2
        except ImportError:
            return {"ok": False, "error": "Install: pip install opencv-python"}

        save_dir = DATASET_DIR / dataset / label
        save_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return {"ok": False, "error": "Cannot open webcam (camera 0)"}

        saved = 0
        try:
            while saved < count:
                ret, frame = cap.read()
                if not ret:
                    break
                ts   = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                path = save_dir / f"{label}_{ts}.jpg"
                cv2.imwrite(str(path), frame)
                saved += 1
                if progress_cb:
                    progress_cb(saved, count, str(path))
                time.sleep(delay_s)
        finally:
            cap.release()

        logger.info(f"Captured {saved} images → {save_dir}")
        return {
            "ok": True,
            "saved": saved,
            "dataset": dataset,
            "label": label,
            "path": str(save_dir),
        }

    # ── Core Training ─────────────────────────────────────────────────────────
    async def train_classifier(
        self,
        dataset_name: str,
        model_name: str = "jarvis_classifier",
        backbone: str = "resnet18",        # resnet18 | efficientnet_b0 | mobilenet_v3_small
        epochs: int = 20,
        batch_size: int = 32,
        lr: float = 1e-3,
        val_split: float = 0.2,
        progress_cb: Callable[[dict], None] | None = None,
    ) -> dict:
        """
        Train an image classifier on a local dataset with GPU acceleration.
        Returns training run details including best accuracy and saved model path.
        """
        import uuid
        run = TrainingRun(
            id=uuid.uuid4().hex[:8],
            model_name=model_name,
            dataset=dataset_name,
            epochs=epochs,
            batch_size=batch_size,
            lr=lr,
        )
        self._runs[run.id] = run
        self._save_run(run)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._train_sync(run, backbone, val_split, progress_cb)
        )
        return result

    def _train_sync(self, run: TrainingRun, backbone: str,
                    val_split: float, progress_cb) -> dict:
        try:
            import torch
            import torch.nn as nn
            import torch.optim as optim
            from torch.utils.data import DataLoader, random_split
            from torchvision import datasets, models, transforms
        except ImportError:
            run.status = "failed"
            run.error  = "PyTorch not installed. Run: python setup_gpu.py"
            self._save_run(run)
            return {"ok": False, "error": run.error, "run_id": run.id}

        device = _get_device() or torch.device("cpu")
        ds_path = DATASET_DIR / run.dataset

        if not ds_path.exists():
            run.status = "failed"
            run.error  = f"Dataset not found: {ds_path}"
            self._save_run(run)
            return {"ok": False, "error": run.error, "run_id": run.id}

        # ── Transforms ───────────────────────────────────────────────────────
        train_tf = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        val_tf = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

        # ── Dataset loading ───────────────────────────────────────────────────
        try:
            full_ds = datasets.ImageFolder(str(ds_path), transform=train_tf)
            if len(full_ds) < 4:
                run.status = "failed"
                run.error  = "Dataset has fewer than 4 images"
                self._save_run(run)
                return {"ok": False, "error": run.error, "run_id": run.id}

            val_size  = max(1, int(len(full_ds) * val_split))
            train_size = len(full_ds) - val_size
            train_ds, val_ds = random_split(full_ds, [train_size, val_size])
            val_ds.dataset.transform = val_tf

            num_classes = len(full_ds.classes)
            logger.info(f"[{run.id}] Classes: {full_ds.classes} | Train: {train_size} | Val: {val_size}")

        except Exception as e:
            run.status = "failed"
            run.error  = f"Dataset loading error: {e}"
            self._save_run(run)
            return {"ok": False, "error": run.error, "run_id": run.id}

        bs = min(run.batch_size, train_size)
        train_loader = DataLoader(train_ds, batch_size=bs, shuffle=True,
                                  num_workers=0, pin_memory=(str(device) == "cuda"))
        val_loader   = DataLoader(val_ds,   batch_size=bs, shuffle=False,
                                  num_workers=0, pin_memory=(str(device) == "cuda"))

        # ── Model (transfer learning) ─────────────────────────────────────────
        try:
            model = self._build_model(backbone, num_classes)
            model = model.to(device)
        except Exception as e:
            run.status = "failed"
            run.error  = f"Model build error: {e}"
            self._save_run(run)
            return {"ok": False, "error": run.error, "run_id": run.id}

        # ── Optimizer + scheduler ─────────────────────────────────────────────
        criterion  = nn.CrossEntropyLoss()
        optimizer  = optim.AdamW(model.parameters(), lr=run.lr, weight_decay=1e-4)
        scheduler  = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=run.epochs)

        # ── Training loop ─────────────────────────────────────────────────────
        run.status = "training"
        self._save_run(run)
        best_wts   = None

        for epoch in range(1, run.epochs + 1):
            # Train phase
            model.train()
            t_loss, t_correct, t_total = 0.0, 0, 0
            for imgs, labels in train_loader:
                imgs, labels = imgs.to(device), labels.to(device)
                optimizer.zero_grad()
                out = model(imgs)
                loss = criterion(out, labels)
                loss.backward()
                optimizer.step()
                t_loss    += loss.item() * imgs.size(0)
                t_correct += (out.argmax(1) == labels).sum().item()
                t_total   += imgs.size(0)

            # Val phase
            model.eval()
            v_loss, v_correct, v_total = 0.0, 0, 0
            import torch as _torch
            with _torch.no_grad():
                for imgs, labels in val_loader:
                    imgs, labels = imgs.to(device), labels.to(device)
                    out   = model(imgs)
                    loss  = criterion(out, labels)
                    v_loss    += loss.item() * imgs.size(0)
                    v_correct += (out.argmax(1) == labels).sum().item()
                    v_total   += imgs.size(0)

            train_acc = t_correct / max(1, t_total)
            val_acc   = v_correct / max(1, v_total)
            train_loss = t_loss   / max(1, t_total)
            val_loss   = v_loss   / max(1, v_total)
            scheduler.step()

            epoch_data = {
                "epoch": epoch, "train_loss": round(train_loss, 4),
                "train_acc": round(train_acc, 4),
                "val_loss": round(val_loss, 4),
                "val_acc": round(val_acc, 4),
            }
            run.log.append(epoch_data)
            run.total_epochs_done = epoch
            self._save_epoch(run.id, epoch, train_loss, train_acc, val_loss, val_acc)

            if val_acc > run.best_acc:
                run.best_acc   = round(val_acc, 4)
                run.best_epoch = epoch
                best_wts = {k: v.cpu().clone() for k, v in model.state_dict().items()}

            logger.info(
                f"[{run.id}] Epoch {epoch}/{run.epochs} — "
                f"loss={train_loss:.4f} acc={train_acc:.3f} | "
                f"val_loss={val_loss:.4f} val_acc={val_acc:.3f}"
            )
            if progress_cb:
                progress_cb(epoch_data)

        # ── Save best model ───────────────────────────────────────────────────
        import torch as _torch
        save_path = MODELS_DIR / f"{run.model_name}_{run.id}.pt"
        payload = {
            "model_state": best_wts,
            "classes": full_ds.classes,
            "backbone": backbone,
            "num_classes": num_classes,
            "best_acc": run.best_acc,
            "run_id": run.id,
            "trained_at": datetime.now().isoformat(),
        }
        _torch.save(payload, str(save_path))
        run.model_path = str(save_path)
        run.status = "done"
        run.finished = datetime.now().isoformat()
        self._save_run(run)

        logger.info(f"[{run.id}] Training complete. Best val_acc={run.best_acc:.3f} @ epoch {run.best_epoch}")
        return {
            "ok": True,
            "run_id": run.id,
            "model_path": str(save_path),
            "classes": full_ds.classes,
            "best_acc": run.best_acc,
            "best_epoch": run.best_epoch,
            "epochs_done": run.total_epochs_done,
        }

    def _build_model(self, backbone: str, num_classes: int):
        """Build a pretrained torchvision model with custom classifier head."""
        from torchvision import models
        import torch.nn as nn

        if backbone == "resnet18":
            m = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
            m.fc = nn.Linear(m.fc.in_features, num_classes)
        elif backbone == "resnet50":
            m = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
            m.fc = nn.Linear(m.fc.in_features, num_classes)
        elif backbone == "efficientnet_b0":
            m = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
            m.classifier[1] = nn.Linear(m.classifier[1].in_features, num_classes)
        elif backbone == "mobilenet_v3_small":
            m = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
            m.classifier[3] = nn.Linear(m.classifier[3].in_features, num_classes)
        else:
            raise ValueError(f"Unknown backbone: {backbone}")
        return m

    # ── Inference ─────────────────────────────────────────────────────────────
    async def predict(self, model_path: str, image_path: str) -> dict:
        """Run inference on a single image with a saved model."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._predict_sync(model_path, image_path)
        )

    def _predict_sync(self, model_path: str, image_path: str) -> dict:
        try:
            import torch
            from torchvision import transforms
            from PIL import Image

            payload = torch.load(model_path, map_location="cpu")
            backbone    = payload.get("backbone", "resnet18")
            classes     = payload["classes"]
            num_classes = payload["num_classes"]

            model = self._build_model(backbone, num_classes)
            model.load_state_dict(payload["model_state"])
            model.eval()

            device = _get_device() or torch.device("cpu")
            model  = model.to(device)

            tf = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])
            img    = Image.open(image_path).convert("RGB")
            tensor = tf(img).unsqueeze(0).to(device)

            with torch.no_grad():
                out   = model(tensor)
                probs = torch.softmax(out, dim=1)[0]

            top_idx   = int(probs.argmax())
            top_label = classes[top_idx]
            top_conf  = float(probs[top_idx])

            return {
                "ok": True,
                "label": top_label,
                "confidence": round(top_conf, 4),
                "all_probs": {cls: round(float(probs[i]), 4) for i, cls in enumerate(classes)},
            }
        except ImportError as e:
            return {"ok": False, "error": f"Missing dependency: {e}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── LLM-Assisted training ──────────────────────────────────────────────────
    async def llm_suggest_hyperparams(self, dataset_info: dict) -> dict:
        """Use local LLM to suggest hyperparameters for a given dataset."""
        if not self.router:
            return {"ok": False, "error": "LLM router not available"}

        prompt = (
            f"You are an expert ML engineer. Given this image classification dataset:\n"
            f"  - Classes: {dataset_info.get('classes')}\n"
            f"  - Total images: {dataset_info.get('num_images')}\n"
            f"  - Num classes: {dataset_info.get('num_classes')}\n\n"
            f"Suggest optimal hyperparameters and backbone. Return ONLY JSON:\n"
            f"{{\n"
            f'  "backbone": "resnet18|efficientnet_b0|mobilenet_v3_small",\n'
            f'  "epochs": 20,\n'
            f'  "batch_size": 32,\n'
            f'  "lr": 0.001,\n'
            f'  "val_split": 0.2,\n'
            f'  "reasoning": "brief explanation"\n'
            f"}}"
        )
        try:
            raw = await self.router.complete_async(
                prompt, temperature=0.1, max_tokens=256,
                force_model="deepseek-coder"
            )
            raw   = raw.strip().replace("```json", "").replace("```", "").strip()
            s, e  = raw.find("{"), raw.rfind("}") + 1
            if s < 0:
                return {"ok": False, "error": "LLM returned no JSON"}
            params = json.loads(raw[s:e])
            params["ok"] = True
            return params
        except Exception as err:
            return {"ok": False, "error": str(err)}

    async def llm_generate_training_script(self, dataset_name: str,
                                            task_description: str) -> dict:
        """Ask DeepSeek Coder to generate a custom training script."""
        if not self.router:
            return {"ok": False, "error": "LLM router not available"}

        prompt = (
            f"Write a complete, executable PyTorch training script for this task:\n"
            f"  Dataset: {dataset_name}\n"
            f"  Task: {task_description}\n\n"
            f"Requirements:\n"
            f"  - Use torchvision transforms and DataLoader\n"
            f"  - Pretrained backbone (resnet18 or efficientnet_b0)\n"
            f"  - GPU support (device = cuda if available)\n"
            f"  - Training + validation loop with accuracy tracking\n"
            f"  - Save best model as .pt file\n"
            f"  - No external API calls\n\n"
            f"Return only the Python code."
        )
        try:
            code = await self.router.complete_async(
                prompt, temperature=0.15, max_tokens=1500,
                force_model="deepseek-coder"
            )
            return {"ok": True, "code": code, "dataset": dataset_name}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def llm_analyze_training_logs(self, run_id: str) -> dict:
        """Ask LLM to analyze training logs and suggest improvements."""
        if not self.router:
            return {"ok": False, "error": "LLM router not available"}

        run = self._runs.get(run_id)
        if not run:
            # Try loading from DB
            try:
                with sqlite3.connect(TRAIN_DB) as c:
                    rows = c.execute(
                        "SELECT epoch,loss,acc,val_loss,val_acc FROM epoch_logs WHERE run_id=? ORDER BY epoch",
                        (run_id,)
                    ).fetchall()
                log = [{"epoch": r[0], "train_loss": r[1], "train_acc": r[2],
                        "val_loss": r[3], "val_acc": r[4]} for r in rows]
            except Exception:
                return {"ok": False, "error": f"Run {run_id} not found"}
        else:
            log = run.log

        if not log:
            return {"ok": False, "error": "No epoch logs found for this run"}

        summary = json.dumps(log[-10:], indent=2)  # Last 10 epochs
        prompt = (
            f"Analyze these neural network training logs (last 10 epochs):\n{summary}\n\n"
            f"Identify:\n"
            f"1. Is the model overfitting, underfitting, or converging well?\n"
            f"2. What should be changed for better performance?\n"
            f"3. Specific hyperparameter recommendations.\n\n"
            f"Be concise (3-5 sentences)."
        )
        try:
            analysis = await self.router.complete_async(
                prompt, temperature=0.2, max_tokens=300,
                force_model="llama3.2"
            )
            return {"ok": True, "analysis": analysis, "run_id": run_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── History + status ──────────────────────────────────────────────────────
    def get_run_status(self, run_id: str) -> dict:
        run = self._runs.get(run_id)
        if run:
            return run.to_dict()
        try:
            with sqlite3.connect(TRAIN_DB) as c:
                row = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row:
                return dict(zip(
                    ["id","model_name","dataset","epochs","batch_size","lr","status",
                     "best_acc","best_epoch","total_done","error","model_path","started","finished"],
                    row
                ))
        except Exception:
            pass
        return {"error": f"Run {run_id} not found"}

    def list_runs(self, limit: int = 20) -> list[dict]:
        try:
            with sqlite3.connect(TRAIN_DB) as c:
                rows = c.execute(
                    "SELECT id,model_name,dataset,status,best_acc,best_epoch,started,finished "
                    "FROM runs ORDER BY started DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [
                dict(zip(["id","model_name","dataset","status","best_acc",
                          "best_epoch","started","finished"], r))
                for r in rows
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def list_models(self) -> list[dict]:
        """List all saved trained model files."""
        models_list = []
        for pt_file in MODELS_DIR.glob("*.pt"):
            stat = pt_file.stat()
            models_list.append({
                "name": pt_file.stem,
                "path": str(pt_file),
                "size_mb": round(stat.st_size / 1e6, 2),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        return sorted(models_list, key=lambda x: x["modified"], reverse=True)


__all__ = ["TrainingEngine"]
