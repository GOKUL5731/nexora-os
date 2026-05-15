"""
JARVIS Phase 2 — GPU Manager
==============================
Monitors and manages RTX 4050 GPU resources for deep learning tasks.
Provides:
  - Real-time VRAM / GPU utilization
  - Training pause/resume based on resource thresholds
  - Device selection per task
  - Thermal monitoring
  - Background training coordinator

Usage:
    from core.phase2.gpu_manager import GPUManager
    gm = GPUManager()
    info = gm.get_gpu_info()
    available = gm.is_training_safe()
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("jarvis.phase2.gpu_manager")


class GPUManager:
    """
    Manages RTX 4050 resources for JARVIS deep learning tasks.
    Thread-safe monitoring with automatic resource gating.
    """

    # Thresholds for RTX 4050 (6GB VRAM)
    VRAM_SAFE_PCT   = 80   # % VRAM usage below which training is allowed
    GPU_SAFE_PCT    = 85   # % GPU utilization below which training is allowed
    TEMP_SAFE_C     = 83   # Temperature (°C) below which training is safe

    def __init__(self):
        self._nvml_ok    = False
        self._handle     = None
        self._lock       = threading.Lock()
        self._history: List[Dict] = []
        self._monitor_thread: Optional[threading.Thread] = None
        self._running    = False
        self._init_nvml()

    def _init_nvml(self):
        try:
            import warnings
            # nvidia-ml-py is the correct package; pynvml is deprecated
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                try:
                    import nvidia_ml_py as pynvml
                except ImportError:
                    import pynvml  # legacy fallback
            pynvml.nvmlInit()
            self._handle  = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._nvml_ok = True
            self._pynvml  = pynvml
            name = pynvml.nvmlDeviceGetName(self._handle)
            if isinstance(name, bytes):
                name = name.decode()
            logger.info(f"[GPU] NVML initialized. Device: {name}")
        except Exception as e:
            self._pynvml = None
            logger.info(f"[GPU] NVML not available: {e}. GPU stats will be estimated.")

    def get_gpu_info(self) -> Dict:
        """Get comprehensive GPU status."""
        info: Dict = {
            "timestamp":  datetime.now().isoformat(),
            "available":  False,
            "name":       "N/A",
            "gpu_pct":    0,
            "vram_used_mb":  0,
            "vram_total_mb": 0,
            "vram_pct":   0,
            "temp_c":     0,
            "power_w":    0,
            "fan_pct":    0,
        }

        if self._nvml_ok and self._handle and self._pynvml:
            try:
                pynvml = self._pynvml
                with self._lock:
                    util  = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
                    mem   = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
                    name  = pynvml.nvmlDeviceGetName(self._handle)
                    if isinstance(name, bytes):
                        name = name.decode()

                vram_used  = mem.used / 1e6
                vram_total = mem.total / 1e6
                vram_pct   = int(mem.used / mem.total * 100)

                info.update({
                    "available":     True,
                    "name":          name,
                    "gpu_pct":       util.gpu,
                    "vram_used_mb":  round(vram_used, 0),
                    "vram_total_mb": round(vram_total, 0),
                    "vram_pct":      vram_pct,
                })

                # Temperature (may not always be available)
                try:
                    temp = pynvml.nvmlDeviceGetTemperature(
                        self._handle, pynvml.NVML_TEMPERATURE_GPU
                    )
                    info["temp_c"] = temp
                except Exception:
                    pass

                # Power
                try:
                    pw = pynvml.nvmlDeviceGetPowerUsage(self._handle)
                    info["power_w"] = round(pw / 1000.0, 1)
                except Exception:
                    pass

                # Fan speed
                try:
                    fan = pynvml.nvmlDeviceGetFanSpeed(self._handle)
                    info["fan_pct"] = fan
                except Exception:
                    pass

                return info

            except Exception as e:
                logger.warning(f"[GPU] NVML query failed: {e}")

        # Fallback: use torch
        try:
            import torch
            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                mem_alloc = torch.cuda.memory_allocated(0)
                mem_total = props.total_memory
                info.update({
                    "available":     True,
                    "name":          props.name,
                    "vram_used_mb":  round(mem_alloc / 1e6, 0),
                    "vram_total_mb": round(mem_total / 1e6, 0),
                    "vram_pct":      int(mem_alloc / mem_total * 100),
                })
        except Exception:
            pass

        return info

    def is_training_safe(self, require_vram_mb: int = 2000) -> Dict:
        """
        Check if it's safe to start GPU training.

        Args:
            require_vram_mb: Estimated VRAM needed for training job

        Returns:
            dict with 'safe' bool and 'reason'
        """
        info = self.get_gpu_info()

        if not info["available"]:
            return {"safe": True, "reason": "cpu_fallback", "device": "cpu"}

        vram_free_mb = info["vram_total_mb"] - info["vram_used_mb"]
        if vram_free_mb < require_vram_mb:
            return {
                "safe":    False,
                "reason":  f"Insufficient VRAM: {vram_free_mb:.0f}MB free, {require_vram_mb}MB needed",
                "free_mb": vram_free_mb,
            }

        if info["vram_pct"] > self.VRAM_SAFE_PCT:
            return {
                "safe":    False,
                "reason":  f"VRAM usage too high: {info['vram_pct']}% (threshold: {self.VRAM_SAFE_PCT}%)",
                "vram_pct": info["vram_pct"],
            }

        if info["gpu_pct"] > self.GPU_SAFE_PCT:
            return {
                "safe":    False,
                "reason":  f"GPU already busy: {info['gpu_pct']}% (threshold: {self.GPU_SAFE_PCT}%)",
                "gpu_pct": info["gpu_pct"],
            }

        temp = info.get("temp_c", 0)
        if temp > self.TEMP_SAFE_C:
            return {
                "safe":    False,
                "reason":  f"GPU temperature too high: {temp}°C (threshold: {self.TEMP_SAFE_C}°C)",
                "temp_c":  temp,
            }

        return {
            "safe":      True,
            "reason":    "Resources available",
            "device":    "cuda",
            "vram_free_mb": round(vram_free_mb, 0),
            "gpu_pct":   info["gpu_pct"],
            "vram_pct":  info["vram_pct"],
        }

    def suggest_batch_size(
        self,
        arch: str = "mobilenet_v3_small",
        img_size: int = 224,
    ) -> int:
        """
        Suggest optimal batch size based on available VRAM.
        Calibrated for RTX 4050 6GB with common architectures.
        """
        info      = self.get_gpu_info()
        vram_free = info.get("vram_free_mb", 0) if info.get("available") else 0

        # Approximate VRAM per sample at 224x224 for different models
        vram_per_sample_mb = {
            "custom_cnn":         0.5,
            "mobilenet_v3_small": 0.8,
            "mobilenet_v3_large": 1.5,
            "resnet18":           1.2,
            "resnet50":           2.5,
        }.get(arch, 1.5)

        if vram_free < 500:
            return 8  # minimal

        # Reserve 1.5GB for model weights + overhead
        usable = max(0, vram_free - 1500)
        batch  = int(usable / vram_per_sample_mb)
        # Round to nearest power of 2
        batch  = max(8, min(128, batch))
        for p2 in [8, 16, 32, 64, 128]:
            if p2 >= batch:
                return p2
        return 32

    def start_monitoring(self, interval_s: float = 5.0):
        """Start background GPU monitoring thread."""
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_s,),
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info(f"[GPU] Monitoring started (interval={interval_s}s)")

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._running = False

    def _monitor_loop(self, interval_s: float):
        while self._running:
            info = self.get_gpu_info()
            with self._lock:
                self._history.append(info)
                if len(self._history) > 1000:  # keep last 1000 snapshots
                    self._history = self._history[-1000:]

            # Log warnings
            if info.get("temp_c", 0) > self.TEMP_SAFE_C:
                logger.warning(f"[GPU] HIGH TEMP: {info['temp_c']}°C")
            if info.get("vram_pct", 0) > 95:
                logger.warning(f"[GPU] VRAM CRITICAL: {info['vram_pct']}%")

            time.sleep(interval_s)

    def get_history(self, last_n: int = 60) -> List[Dict]:
        """Return last N GPU monitoring snapshots."""
        with self._lock:
            return self._history[-last_n:]

    def get_summary(self) -> Dict:
        """Average stats from monitoring history."""
        history = self.get_history(20)
        if not history:
            return self.get_gpu_info()

        avgs = {
            "avg_gpu_pct":  round(sum(h.get("gpu_pct", 0) for h in history) / len(history), 1),
            "avg_vram_pct": round(sum(h.get("vram_pct", 0) for h in history) / len(history), 1),
            "avg_temp_c":   round(sum(h.get("temp_c", 0) for h in history) / len(history), 1),
            "max_temp_c":   max(h.get("temp_c", 0) for h in history),
            "samples":      len(history),
        }
        avgs.update(self.get_gpu_info())
        return avgs

    def cleanup_vram(self):
        """Free unused CUDA cache."""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("[GPU] CUDA cache cleared")
        except Exception:
            pass

    def shutdown(self):
        """Cleanup NVML."""
        self.stop_monitoring()
        if self._nvml_ok and self._pynvml:
            try:
                self._pynvml.nvmlShutdown()
            except Exception:
                pass


# ─── Background Training Coordinator ────────────────────────────────────────────
class BackgroundTrainingCoordinator:
    """
    Manages background training jobs for JARVIS Phase 2.
    Automatically pauses if GPU resources are strained,
    saves checkpoints, and resumes when resources are free.
    """

    def __init__(self, gpu_manager: GPUManager):
        self.gpu        = gpu_manager
        self._trainer   = None
        self._paused    = False
        self._watcher   = None
        self._running   = False
        self._history:  List[Dict] = []

    def set_trainer(self, trainer):
        """Attach a VisionTrainer instance."""
        self._trainer = trainer

    def start_background_watch(self, check_interval_s: float = 30.0):
        """Watch GPU health during training and pause if needed."""
        if self._running:
            return
        self._running = True
        self._watcher = threading.Thread(
            target=self._watch_loop,
            args=(check_interval_s,),
            daemon=True,
        )
        self._watcher.start()
        logger.info("[BackgroundTrainer] GPU watchdog started")

    def _watch_loop(self, interval_s: float):
        while self._running:
            if self._trainer and self._trainer.state.is_training:
                safety = self.gpu.is_training_safe()
                if not safety["safe"] and not self._paused:
                    logger.warning(f"[BackgroundTrainer] Pausing training: {safety['reason']}")
                    self._trainer.stop_training()
                    self._paused = True
                    self._history.append({
                        "action": "pause",
                        "reason": safety["reason"],
                        "ts": datetime.now().isoformat(),
                    })
                elif safety["safe"] and self._paused:
                    logger.info("[BackgroundTrainer] Resources recovered. Training can resume.")
                    self._paused = False
                    self._history.append({
                        "action": "resume_available",
                        "ts": datetime.now().isoformat(),
                    })
            time.sleep(interval_s)

    def stop(self):
        self._running = False

    def get_history(self) -> List[Dict]:
        return list(self._history)

    def is_paused(self) -> bool:
        return self._paused

    def get_status(self) -> Dict:
        gpu_info = self.gpu.get_gpu_info()
        training = self._trainer.state.snapshot() if self._trainer else {}
        return {
            "is_training": training.get("is_training", False),
            "paused":      self._paused,
            "gpu":         gpu_info,
            "training":    training,
        }
