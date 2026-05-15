"""
JARVIS Phase 2 — Vision Training Pipeline
==========================================
Local CNN training system supporting:
  - Custom dataset from webcam or file system
  - ResNet18 / ResNet50 / MobileNetV3 architectures
  - Transfer learning with fine-tuning
  - Train/validation split
  - GPU-accelerated training (RTX 4050)
  - Mixed-precision training (FP16) for faster throughput
  - Checkpoint saving/resuming
  - Accuracy & loss history
  - Background training with progress callbacks

Usage:
    from core.phase2.vision_training import VisionTrainer
    trainer = VisionTrainer()
    result = await trainer.train(
        dataset_dir="datasets/",
        arch="mobilenet_v3_small",
        epochs=10,
        batch_size=32,
    )
"""

import asyncio
import json
import logging
import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("jarvis.phase2.vision_training")

ROOT         = Path(__file__).resolve().parent.parent.parent
DATASETS_DIR = ROOT / "datasets"
MODELS_DIR   = ROOT / "models"
CKPT_DIR     = ROOT / "checkpoints"
LOG_DIR      = ROOT / "training_logs"

for _d in [DATASETS_DIR, MODELS_DIR, CKPT_DIR, LOG_DIR]:
    _d.mkdir(parents=True, exist_ok=True)


# ─── Dataset Preparation ───────────────────────────────────────────────────────
def _build_imagefolder_dataset(
    dataset_dir: str,
    val_split: float = 0.2,
    img_size: int = 224,
):
    """
    Build torchvision ImageFolder datasets from a directory.
    Expected structure:
        dataset_dir/
            class_a/
                img1.jpg ...
            class_b/
                img2.jpg ...

    Returns (train_dataset, val_dataset, class_names)
    """
    try:
        from torchvision import datasets, transforms
        from torch.utils.data import random_split

        train_tfm = transforms.Compose([
            transforms.Resize((img_size + 32, img_size + 32)),
            transforms.RandomCrop(img_size),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2),
            transforms.RandomRotation(15),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        val_tfm = transforms.Compose([
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

        full_ds = datasets.ImageFolder(dataset_dir, transform=train_tfm)
        class_names = full_ds.classes

        if len(full_ds) < 4:
            raise ValueError(f"Too few images in dataset ({len(full_ds)}). Need at least 4.")

        val_size   = max(1, int(len(full_ds) * val_split))
        train_size = len(full_ds) - val_size

        train_ds, val_ds = random_split(full_ds, [train_size, val_size])
        # Apply val transforms to val subset
        val_ds.dataset = datasets.ImageFolder(dataset_dir, transform=val_tfm)

        return train_ds, val_ds, class_names
    except ImportError as e:
        raise ImportError(f"torchvision required: {e}. Install: pip install torchvision")


# ─── Model Factory ──────────────────────────────────────────────────────────────
def _build_model(arch: str, num_classes: int, pretrained: bool = True):
    """Create a torchvision model with custom head for num_classes."""
    import torch.nn as nn
    import torchvision.models as models

    if arch == "resnet18":
        weights = models.ResNet18_Weights.DEFAULT if pretrained else None
        m = models.resnet18(weights=weights)
        m.fc = nn.Linear(m.fc.in_features, num_classes)

    elif arch == "resnet50":
        weights = models.ResNet50_Weights.DEFAULT if pretrained else None
        m = models.resnet50(weights=weights)
        m.fc = nn.Linear(m.fc.in_features, num_classes)

    elif arch == "mobilenet_v3_small":
        weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        m = models.mobilenet_v3_small(weights=weights)
        m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, num_classes)

    elif arch == "mobilenet_v3_large":
        weights = models.MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
        m = models.mobilenet_v3_large(weights=weights)
        m.classifier[-1] = nn.Linear(m.classifier[-1].in_features, num_classes)

    elif arch == "custom_cnn":
        # Lightweight custom CNN for small datasets
        m = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.AdaptiveAvgPool2d((4, 4)),
            nn.Flatten(),
            nn.Linear(128 * 16, 256), nn.ReLU(), nn.Dropout(0.4),
            nn.Linear(256, num_classes),
        )
    else:
        raise ValueError(f"Unknown architecture: {arch}. "
                         "Choices: resnet18, resnet50, mobilenet_v3_small, mobilenet_v3_large, custom_cnn")

    return m


# ─── Training State ─────────────────────────────────────────────────────────────
class TrainingState:
    """Mutable training progress shared between background thread and UI."""

    def __init__(self):
        self.is_training  = False
        self.epoch        = 0
        self.total_epochs = 0
        self.train_loss   = 0.0
        self.val_loss     = 0.0
        self.train_acc    = 0.0
        self.val_acc      = 0.0
        self.best_acc     = 0.0
        self.history: List[Dict] = []
        self.status       = "idle"
        self.message      = ""
        self.lock         = threading.Lock()

    def update(self, **kwargs):
        with self.lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def snapshot(self) -> Dict:
        with self.lock:
            return {
                "is_training":  self.is_training,
                "epoch":        self.epoch,
                "total_epochs": self.total_epochs,
                "train_loss":   round(self.train_loss, 4),
                "val_loss":     round(self.val_loss, 4),
                "train_acc":    round(self.train_acc, 2),
                "val_acc":      round(self.val_acc, 2),
                "best_acc":     round(self.best_acc, 2),
                "status":       self.status,
                "message":      self.message,
                "history":      self.history.copy(),
            }


# ─── Vision Trainer ─────────────────────────────────────────────────────────────
class VisionTrainer:
    """
    Local CNN training pipeline with GPU support.
    Supports background training, checkpointing, and resume.
    """

    def __init__(self, config: dict = None):
        self.config  = config or {}
        self.state   = TrainingState()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ── Sync training loop ──────────────────────────────────────────────────────
    def _train_loop(
        self,
        dataset_dir: str,
        arch: str,
        epochs: int,
        batch_size: int,
        lr: float,
        val_split: float,
        resume_from: Optional[str],
        save_name: str,
        progress_cb: Optional[Callable],
    ):
        """Core training loop (runs in a background thread)."""
        import torch
        from torch.utils.data import DataLoader
        import torch.nn as nn
        import torch.optim as optim

        self.state.update(is_training=True, status="initializing", total_epochs=epochs)

        try:
            device_str = "cuda" if torch.cuda.is_available() else "cpu"
            device     = torch.device(device_str)
            logger.info(f"[Trainer] Using device: {device_str}")

            # Dataset
            self.state.update(message="Building dataset...")
            train_ds, val_ds, class_names = _build_imagefolder_dataset(
                dataset_dir, val_split=val_split
            )
            num_classes = len(class_names)
            logger.info(f"[Trainer] Classes: {class_names} | "
                        f"Train: {len(train_ds)} | Val: {len(val_ds)}")

            # Auto batch size based on GPU memory
            if device_str == "cuda" and batch_size == "auto":
                vram = torch.cuda.get_device_properties(0).total_memory / 1e9
                batch_size = 64 if vram >= 6 else 32 if vram >= 4 else 16
                logger.info(f"[Trainer] Auto batch_size={batch_size} for {vram:.1f}GB VRAM")

            train_loader = DataLoader(
                train_ds, batch_size=batch_size, shuffle=True,
                num_workers=2, pin_memory=(device_str == "cuda"),
                persistent_workers=True,
            )
            val_loader = DataLoader(
                val_ds, batch_size=batch_size, shuffle=False,
                num_workers=2, pin_memory=(device_str == "cuda"),
                persistent_workers=True,
            )

            # Model
            self.state.update(message=f"Loading {arch}...")
            model = _build_model(arch, num_classes, pretrained=True).to(device)

            start_epoch = 0
            best_acc    = 0.0
            scaler      = None

            # Resume
            if resume_from and Path(resume_from).exists():
                ckpt = torch.load(resume_from, map_location=device)
                model.load_state_dict(ckpt["model_state"])
                start_epoch = ckpt.get("epoch", 0)
                best_acc    = ckpt.get("best_acc", 0.0)
                class_names = ckpt.get("class_names", class_names)
                logger.info(f"[Trainer] Resumed from epoch {start_epoch}")

            # Optimizer & scheduler
            optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
            scheduler = optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=epochs, eta_min=1e-6
            )
            criterion = nn.CrossEntropyLoss()

            # Mixed precision
            use_amp = (device_str == "cuda")
            if use_amp:
                scaler = torch.amp.GradScaler()
                logger.info("[Trainer] Mixed precision (FP16) enabled")

            history  = []
            ckpt_dir = CKPT_DIR / save_name
            ckpt_dir.mkdir(parents=True, exist_ok=True)

            # ── Epoch loop ─────────────────────────────────────────────────────
            for epoch in range(start_epoch, epochs):
                if self._stop_event.is_set():
                    logger.info("[Trainer] Training stopped by request")
                    break

                self.state.update(epoch=epoch + 1, status="training")

                # Train
                model.train()
                train_loss = 0.0
                train_correct = 0
                train_total   = 0

                for batch_idx, (inputs, targets) in enumerate(train_loader):
                    if self._stop_event.is_set():
                        break
                    inputs, targets = inputs.to(device), targets.to(device)

                    optimizer.zero_grad()
                    if use_amp:
                        with torch.amp.autocast(device_type="cuda"):
                            outputs = model(inputs)
                            loss    = criterion(outputs, targets)
                        scaler.scale(loss).backward()
                        scaler.step(optimizer)
                        scaler.update()
                    else:
                        outputs = model(inputs)
                        loss    = criterion(outputs, targets)
                        loss.backward()
                        optimizer.step()

                    train_loss    += loss.item() * inputs.size(0)
                    preds          = outputs.argmax(dim=1)
                    train_correct += (preds == targets).sum().item()
                    train_total   += inputs.size(0)

                scheduler.step()

                t_loss = train_loss / max(train_total, 1)
                t_acc  = 100.0 * train_correct / max(train_total, 1)

                # Validate
                model.eval()
                val_loss    = 0.0
                val_correct = 0
                val_total   = 0

                with torch.no_grad():
                    for inputs, targets in val_loader:
                        inputs, targets = inputs.to(device), targets.to(device)
                        if use_amp:
                            with torch.amp.autocast(device_type="cuda"):
                                outputs = model(inputs)
                                loss    = criterion(outputs, targets)
                        else:
                            outputs = model(inputs)
                            loss    = criterion(outputs, targets)
                        val_loss    += loss.item() * inputs.size(0)
                        preds        = outputs.argmax(dim=1)
                        val_correct += (preds == targets).sum().item()
                        val_total   += inputs.size(0)

                v_loss = val_loss / max(val_total, 1)
                v_acc  = 100.0 * val_correct / max(val_total, 1)

                ep_record = {
                    "epoch":     epoch + 1,
                    "train_loss": round(t_loss, 4),
                    "val_loss":   round(v_loss, 4),
                    "train_acc":  round(t_acc, 2),
                    "val_acc":    round(v_acc, 2),
                    "ts":         datetime.now().isoformat(),
                }
                history.append(ep_record)

                logger.info(
                    f"[Trainer] Epoch {epoch+1}/{epochs} | "
                    f"Train Loss={t_loss:.4f} Acc={t_acc:.1f}% | "
                    f"Val Loss={v_loss:.4f} Acc={v_acc:.1f}%"
                )

                is_best = v_acc > best_acc
                if is_best:
                    best_acc = v_acc

                # Save checkpoint
                ckpt_data = {
                    "epoch":       epoch + 1,
                    "model_state": model.state_dict(),
                    "arch":        arch,
                    "class_names": class_names,
                    "best_acc":    best_acc,
                    "history":     history,
                }
                torch.save(ckpt_data, ckpt_dir / "last.pth")
                if is_best:
                    torch.save(ckpt_data, ckpt_dir / "best.pth")
                    logger.info(f"[Trainer] ✓ New best model: {best_acc:.1f}%")

                # Periodic checkpoint
                if (epoch + 1) % 5 == 0:
                    torch.save(ckpt_data, ckpt_dir / f"epoch_{epoch+1}.pth")

                self.state.update(
                    epoch=epoch + 1,
                    train_loss=t_loss, val_loss=v_loss,
                    train_acc=t_acc,   val_acc=v_acc,
                    best_acc=best_acc,
                    history=history,
                    message=f"Epoch {epoch+1}/{epochs} | ValAcc={v_acc:.1f}%",
                )

                if progress_cb:
                    try:
                        progress_cb(self.state.snapshot())
                    except Exception:
                        pass

            # Save final model
            final_path = MODELS_DIR / f"{save_name}_final.pth"
            torch.save(ckpt_data, final_path)

            # Save training log
            log_path = LOG_DIR / f"{save_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(log_path, "w") as f:
                json.dump({
                    "arch": arch, "epochs": epochs, "batch_size": batch_size,
                    "lr": lr, "best_acc": best_acc, "class_names": class_names,
                    "history": history, "device": device_str,
                }, f, indent=2)

            self.state.update(
                is_training=False,
                status="complete",
                message=f"Training complete! Best val accuracy: {best_acc:.1f}%",
            )
            logger.info(f"[Trainer] Training complete. Best acc={best_acc:.1f}%")

        except Exception as e:
            logger.error(f"[Trainer] Training failed: {e}", exc_info=True)
            self.state.update(
                is_training=False,
                status="error",
                message=str(e),
            )

    # ── Public API ──────────────────────────────────────────────────────────────
    async def train(
        self,
        dataset_dir: Optional[str] = None,
        arch: str = "mobilenet_v3_small",
        epochs: int = 15,
        batch_size: int = 32,
        lr: float = 3e-4,
        val_split: float = 0.2,
        resume_from: Optional[str] = None,
        save_name: str = "jarvis_vision",
        progress_cb: Optional[Callable] = None,
        background: bool = False,
    ) -> Dict:
        """
        Launch CNN training.

        Args:
            dataset_dir:  Path to dataset (ImageFolder structure). Defaults to ROOT/datasets.
            arch:         Model architecture (resnet18/resnet50/mobilenet_v3_small/custom_cnn)
            epochs:       Number of training epochs
            batch_size:   Batch size (use "auto" for GPU auto-detection)
            lr:           Initial learning rate
            val_split:    Fraction of data for validation
            resume_from:  Path to checkpoint to resume from
            save_name:    Name prefix for saved checkpoints/models
            progress_cb:  Optional callback(state_dict) called after each epoch
            background:   If True, train in background thread and return immediately

        Returns:
            Training state dict on completion (or immediately if background=True)
        """
        if self.state.is_training:
            return {"error": "Training already in progress", "status": self.state.snapshot()}

        ds_dir = dataset_dir or str(DATASETS_DIR)
        if not Path(ds_dir).exists():
            return {"error": f"Dataset directory not found: {ds_dir}"}

        # Check dataset has at least 2 classes
        classes = [d for d in Path(ds_dir).iterdir() if d.is_dir()]
        if len(classes) < 2:
            return {
                "error": f"Need at least 2 class subdirectories in {ds_dir}. "
                         f"Found: {[c.name for c in classes]}"
            }

        self._stop_event.clear()
        args = (ds_dir, arch, epochs, batch_size, lr, val_split, resume_from, save_name, progress_cb)

        if background:
            self._thread = threading.Thread(target=self._train_loop, args=args, daemon=True)
            self._thread.start()
            return {"status": "started", "arch": arch, "epochs": epochs, "dataset": ds_dir}

        # Blocking async
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._train_loop, *args)
        return self.state.snapshot()

    def stop_training(self):
        """Request training to stop after current epoch."""
        self._stop_event.set()
        self.state.update(message="Stop requested...")
        logger.info("[Trainer] Stop signal sent")

    def get_status(self) -> Dict:
        """Get current training progress."""
        return self.state.snapshot()

    def list_checkpoints(self, save_name: str) -> List[Dict]:
        """List all saved checkpoints for a run."""
        ckpt_dir = CKPT_DIR / save_name
        if not ckpt_dir.exists():
            return []
        results = []
        for f in sorted(ckpt_dir.glob("*.pth")):
            try:
                import torch
                ckpt = torch.load(f, map_location="cpu")
                results.append({
                    "file":       str(f),
                    "epoch":      ckpt.get("epoch", "?"),
                    "best_acc":   ckpt.get("best_acc", 0.0),
                    "classes":    ckpt.get("class_names", []),
                    "size_mb":    round(f.stat().st_size / 1e6, 2),
                })
            except Exception:
                results.append({"file": str(f), "error": "unreadable"})
        return results

    def list_saved_models(self) -> List[Dict]:
        """List all final trained models."""
        return [
            {
                "name": f.stem,
                "path": str(f),
                "size_mb": round(f.stat().st_size / 1e6, 2),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            }
            for f in sorted(MODELS_DIR.glob("*.pth"))
        ]

    def dataset_info(self, dataset_dir: Optional[str] = None) -> Dict:
        """Return statistics about a dataset directory."""
        ds_dir = Path(dataset_dir or DATASETS_DIR)
        if not ds_dir.exists():
            return {"error": "Directory not found"}

        classes = {}
        total   = 0
        for cls_dir in sorted(ds_dir.iterdir()):
            if cls_dir.is_dir():
                imgs = len(list(cls_dir.glob("*.jpg")) + list(cls_dir.glob("*.png")))
                classes[cls_dir.name] = imgs
                total += imgs

        return {
            "directory":    str(ds_dir),
            "classes":      classes,
            "total_images": total,
            "num_classes":  len(classes),
            "ready":        len(classes) >= 2 and total >= 10,
        }

    def generate_loss_plot(self, history: List[Dict], save_path: Optional[str] = None) -> Optional[str]:
        """Generate accuracy/loss plots using matplotlib. Returns saved path."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            epochs     = [h["epoch"] for h in history]
            train_loss = [h["train_loss"] for h in history]
            val_loss   = [h["val_loss"] for h in history]
            train_acc  = [h["train_acc"] for h in history]
            val_acc    = [h["val_acc"] for h in history]

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
            fig.patch.set_facecolor("#0a0e1a")
            for ax in [ax1, ax2]:
                ax.set_facecolor("#0f1628")
                ax.tick_params(colors="#e8f4ff")
                ax.spines[:].set_color("#1a2a4a")

            ax1.plot(epochs, train_loss, color="#00d4ff", label="Train Loss")
            ax1.plot(epochs, val_loss,   color="#ff4466", label="Val Loss")
            ax1.set_title("Loss",    color="#e8f4ff"); ax1.legend()
            ax1.set_xlabel("Epoch",  color="#e8f4ff")

            ax2.plot(epochs, train_acc, color="#00d4ff", label="Train Acc%")
            ax2.plot(epochs, val_acc,   color="#00ff9d", label="Val Acc%")
            ax2.set_title("Accuracy", color="#e8f4ff"); ax2.legend()
            ax2.set_xlabel("Epoch",   color="#e8f4ff")

            plt.tight_layout()
            dest = save_path or str(LOG_DIR / f"training_plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(dest, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
            plt.close(fig)
            return dest
        except Exception as e:
            logger.warning(f"[Trainer] Plot generation failed: {e}")
            return None
