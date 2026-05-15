"""
JARVIS Phase 2 — Core Orchestrator
=====================================
Ties together all Phase 2 deep learning modules.
Each subsystem is individually guarded — broken CUDA/torch
degrades gracefully without crashing the whole system.
"""

import asyncio
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("jarvis.phase2.core")
ROOT = Path(__file__).resolve().parent.parent.parent


class JARVISPhase2:
    """Main Phase 2 controller. Manages lifecycle and routing for all DL subsystems."""

    def __init__(self, config: dict = None):
        self.config  = config or {}
        self._ready  = False

        self.cnn:        Optional[object] = None
        self.trainer:    Optional[object] = None
        self.rnn:        Optional[object] = None
        self.self_learn: Optional[object] = None
        self.memory:     Optional[object] = None
        self.decision:   Optional[object] = None
        self.gpu:        Optional[object] = None
        self.predictor:  Optional[object] = None
        self._bg_coord:  Optional[object] = None

        self._training_task:    Optional[asyncio.Task] = None
        self._proactive_task:   Optional[asyncio.Task] = None
        self._rnn_retrain_task: Optional[asyncio.Task] = None
        try:
            from core.event_bus import get_event_bus
            self.bus = get_event_bus()
        except Exception:
            self.bus = None

        logger.info("[Phase2] JARVISPhase2 instantiated")

    async def start(self, enable_gpu_monitor: bool = True) -> Dict:
        """
        Initialize all Phase 2 subsystems individually.
        OSError / ImportError from broken CUDA DLLs are caught per-module.
        """
        logger.info("[Phase2] Starting Phase 2 deep learning layer...")
        self._publish("phase2.status", {"status": "starting"})
        errors = []

        # 1. GPU Manager
        try:
            from core.phase2.gpu_manager import GPUManager, BackgroundTrainingCoordinator
            self.gpu = GPUManager()
            if enable_gpu_monitor:
                self.gpu.start_monitoring(interval_s=10.0)
        except Exception as e:
            logger.warning(f"[Phase2] GPU Manager degraded: {e}")
            errors.append(f"gpu: {e}")

        # 2. Multimodal Memory
        try:
            from core.phase2.multimodal_memory import MultimodalMemory
            self.memory = MultimodalMemory(self.config)
        except Exception as e:
            logger.warning(f"[Phase2] Memory degraded: {e}")
            errors.append(f"memory: {e}")

        # 3. CNN Vision Engine  ← most likely to fail with broken torch DLLs
        try:
            from core.phase2.cnn_engine import CNNVisionEngine
            self.cnn = CNNVisionEngine(self.config)
        except (ImportError, OSError) as e:
            logger.warning(f"[Phase2] CNN unavailable (torch/CUDA DLL issue): {e}")
            logger.warning("[Phase2] Vision disabled. Use launcher option [8] to reinstall PyTorch CUDA.")
            errors.append(f"cnn: {type(e).__name__}")
            self.cnn = None
        except Exception as e:
            logger.warning(f"[Phase2] CNN Engine failed: {e}")
            errors.append(f"cnn: {e}")
            self.cnn = None

        # 4. Vision Trainer
        try:
            from core.phase2.vision_training import VisionTrainer
            self.trainer = VisionTrainer(self.config)
        except (ImportError, OSError) as e:
            logger.warning(f"[Phase2] VisionTrainer unavailable: {type(e).__name__}")
            errors.append(f"trainer: {type(e).__name__}")
            self.trainer = None
        except Exception as e:
            logger.warning(f"[Phase2] VisionTrainer failed: {e}")
            errors.append(f"trainer: {e}")
            self.trainer = None

        # 5. RNN Behavior Engine
        try:
            from core.phase2.rnn_engine import BehaviorRNN
            self.rnn = BehaviorRNN(self.config)
            self.rnn.load_if_exists()
        except (ImportError, OSError) as e:
            logger.warning(f"[Phase2] RNN unavailable: {type(e).__name__}")
            errors.append(f"rnn: {type(e).__name__}")
            self.rnn = None
        except Exception as e:
            logger.warning(f"[Phase2] RNN failed: {e}")
            errors.append(f"rnn: {e}")
            self.rnn = None

        # 6. Self-Learning
        try:
            from core.phase2.behavior_learning import SelfImprovementEngine
            self.self_learn = SelfImprovementEngine(self.config)
        except Exception as e:
            logger.warning(f"[Phase2] SelfLearn failed: {e}")
            errors.append(f"self_learn: {e}")

        # 7. Prediction Engine
        try:
            from core.phase2.prediction_engine import PredictionEngine
            self.predictor = PredictionEngine(self.rnn, self.self_learn, self.config)
        except Exception as e:
            logger.warning(f"[Phase2] Prediction Engine failed: {e}")
            errors.append(f"predictor: {e}")

        # 8. Decision Engine
        try:
            from core.phase2.decision_engine import DecisionEngine
            self.decision = DecisionEngine(
                config            = self.config,
                memory            = self.memory,
                cnn_engine        = self.cnn,
                rnn_engine        = self.rnn,
                behavior_learning = self.self_learn,
            )
        except Exception as e:
            logger.warning(f"[Phase2] Decision Engine failed: {e}")
            errors.append(f"decision: {e}")

        # 9. Background coordinator
        try:
            from core.phase2.gpu_manager import BackgroundTrainingCoordinator
            self._bg_coord = BackgroundTrainingCoordinator(self.gpu)
            if self.trainer:
                self._bg_coord.set_trainer(self.trainer)
            self._bg_coord.start_background_watch(check_interval_s=30.0)
        except Exception as e:
            logger.warning(f"[Phase2] BG Coordinator failed: {e}")

        # 10. Background RNN retrain loop
        try:
            self._rnn_retrain_task = asyncio.create_task(self._rnn_retrain_loop())
        except Exception:
            pass

        self._ready = True
        status = "ready" if not errors else "degraded"
        logger.info(f"[Phase2] Online — status={status}, degraded_modules={len(errors)}")
        if errors:
            logger.warning(f"[Phase2] Degraded: {'; '.join(str(e) for e in errors[:3])}")

        result = {
            "status":    status,
            "errors":    errors,
            "gpu":       self.gpu.get_gpu_info() if self.gpu else {"available": False},
            "memory":    self.memory.get_memory_stats() if self.memory else {},
            "rnn_ready": self.rnn.get_stats().get("model_trained", False) if self.rnn else False,
            "cnn_ready": self.cnn is not None,
        }
        self._publish("phase2.status", result)
        return result

    # ── Command Processing ─────────────────────────────────────────────────────
    async def process_command(self, command: str, context: dict = None) -> Dict:
        if not self._ready:
            return {"message": "Phase 2 not ready yet.", "type": "error"}

        cmd = command.strip()
        logger.info(f"[Phase2] Processing: {cmd[:80]}")
        self._publish("phase2.command", {"command": cmd})

        if not self.decision:
            return {"message": "Decision engine offline (torch/CUDA issue).", "type": "error"}

        decision = await self.decision.decide(cmd, use_screen=True, use_camera=False)
        handler  = decision["routing"]["handler"]

        try:
            if handler == "cnn":
                return await self._handle_vision(cmd, decision)
            elif handler == "vision_trainer":
                return await self._handle_training(cmd, decision)
            elif handler == "rnn":
                return await self._handle_rnn(cmd, decision)
            elif handler == "memory_search":
                return await self._handle_memory_search(cmd)
            else:
                return {
                    "message":     decision.get("llm_context", ""),
                    "type":        "context_enriched",
                    "handler":     handler,
                    "routing":     decision["routing"],
                    "phase2_data": {
                        "memory_context":  decision.get("memory_context", ""),
                        "proactive_hints": decision.get("proactive_hints", []),
                        "mode":            decision.get("mode", "normal"),
                    },
                }
        except Exception as e:
            logger.error(f"[Phase2] Handler error: {e}", exc_info=True)
            return {"message": f"Phase 2 error: {e}", "type": "error"}

    # ── Vision Handler ─────────────────────────────────────────────────────────
    async def _handle_vision(self, cmd: str, decision: Dict) -> Dict:
        if not self.cnn:
            return {
                "message": "Vision engine offline. Reinstall PyTorch CUDA (launcher option 8).",
                "type": "warning"
            }
        cmd_lower = cmd.lower()
        if "webcam" in cmd_lower or "camera" in cmd_lower or "see me" in cmd_lower:
            result  = await self.cnn.detect_user_presence()
            faces   = result.get("faces", 0)
            present = result.get("present", False)
            msg     = f"Camera: {'User detected' if present else 'No user detected'}. Faces: {faces}."
            if self.memory:
                self.memory.store_vision_event("webcam", msg, result.get("image", ""))
            return {"message": msg, "type": "vision_result", "phase2_data": result}
        elif any(w in cmd_lower for w in ["screen", "analyze", "describe"]):
            result = await self.cnn.analyze_screen()
            msg    = result.get("scene_summary", "Screen analyzed.")
            if self.memory:
                self.memory.store_vision_event("screen_analysis", msg, result.get("source", ""),
                                               result.get("objects", {}).get("objects", []))
            return {"message": msg, "type": "vision_result", "phase2_data": result}
        elif any(w in cmd_lower for w in ["detect", "objects"]):
            result = await self.cnn.detect_objects()
            count  = result.get("count", 0)
            objs   = result.get("objects", [])
            msg    = f"Detected {count} object(s): {', '.join(objs[:8]) if objs else 'none'}."
            return {"message": msg, "type": "vision_result", "phase2_data": result}
        else:
            result = await self.cnn.analyze_screen()
            return {"message": result.get("scene_summary", "Vision analysis complete."),
                    "type": "vision_result", "phase2_data": result}

    # ── Training Handler ───────────────────────────────────────────────────────
    async def _handle_training(self, cmd: str, decision: Dict) -> Dict:
        if not self.trainer:
            return {"message": "Vision trainer offline (torch issue).", "type": "warning"}
        cmd_lower = cmd.lower()
        if "status" in cmd_lower or "progress" in cmd_lower:
            status = self.trainer.get_status()
            msg = (f"Training: Epoch {status['epoch']}/{status['total_epochs']} | "
                   f"Val Acc: {status['val_acc']:.1f}%"
                   if status.get("is_training") else
                   f"Status: {status['status']}. {status['message']}")
            return {"message": msg, "type": "training_status", "phase2_data": status}
        elif "stop" in cmd_lower or "cancel" in cmd_lower:
            self.trainer.stop_training()
            return {"message": "Training stop requested.", "type": "info"}
        elif "collect" in cmd_lower or "dataset" in cmd_lower:
            words = cmd_lower.split()
            label = "unlabeled"
            for kw in ["for", "label", "class"]:
                if kw in words:
                    idx = words.index(kw)
                    if idx + 1 < len(words):
                        label = words[idx + 1]; break
            if self.cnn:
                asyncio.create_task(self.cnn.start_dataset_capture(label=label, count=30, interval_ms=500))
                return {"message": f"Capturing 30 images for class '{label}'.", "type": "dataset_capture"}
            return {"message": "CNN offline, cannot capture.", "type": "warning"}
        elif "train" in cmd_lower:
            if not self.gpu:
                return {"message": "GPU manager offline.", "type": "warning"}
            safety = self.gpu.is_training_safe()
            if not safety["safe"]:
                return {"message": f"Cannot train: {safety['reason']}", "type": "warning"}
            ds_info = self.trainer.dataset_info()
            if not ds_info.get("ready", False):
                return {"message": f"Dataset not ready ({ds_info.get('num_classes',0)} classes). Collect data first.",
                        "type": "warning", "phase2_data": ds_info}
            arch  = "mobilenet_v3_small"
            batch = self.gpu.suggest_batch_size(arch)
            asyncio.create_task(self.trainer.train(arch=arch, epochs=15, batch_size=batch, background=False))
            return {"message": f"Training started: arch={arch}, batch={batch}.", "type": "training_started"}
        else:
            ds_info = self.trainer.dataset_info()
            return {"message": f"Vision system ready. {ds_info.get('num_classes',0)} classes, "
                               f"{ds_info.get('total_images',0)} images.",
                    "type": "info", "phase2_data": ds_info}

    # ── RNN Handler ────────────────────────────────────────────────────────────
    async def _handle_rnn(self, cmd: str, decision: Dict) -> Dict:
        if not self.rnn:
            return {"message": "RNN engine offline.", "type": "warning"}
        cmd_lower = cmd.lower()
        if "routine" in cmd_lower or "pattern" in cmd_lower:
            patterns = self.rnn.get_routine_patterns()
            top_cmds = patterns.get("top_commands", [])[:5]
            lines    = [f"- {c['command'].replace('_',' ')} ({c['count']}x)" for c in top_cmds]
            msg      = ("Your routines:\n" + "\n".join(lines)) if lines else "No patterns yet."
            return {"message": msg, "type": "routine_analysis", "phase2_data": patterns}
        elif "predict" in cmd_lower or "next" in cmd_lower:
            pred = self.predictor.predict_next_action() if self.predictor else {}
            top  = pred.get("top")
            msg  = (f"Predicted next: {top['command'].replace('_',' ')} ({top['confidence']:.0%})"
                    if top else "Not enough data for prediction.")
            return {"message": msg, "type": "prediction", "phase2_data": pred}
        elif "train" in cmd_lower or "retrain" in cmd_lower:
            result = await self.rnn.train_on_history(epochs=20)
            return {"message": f"RNN trained. Events: {result.get('events',0)}, "
                               f"Loss: {result.get('best_loss','N/A')}",
                    "type": "rnn_trained", "phase2_data": result}
        else:
            stats = self.rnn.get_stats()
            return {"message": f"RNN: {stats['total_events']} events, "
                               f"{stats['unique_commands']} commands recorded.",
                    "type": "rnn_stats", "phase2_data": stats}

    # ── Memory Search Handler ──────────────────────────────────────────────────
    async def _handle_memory_search(self, cmd: str) -> Dict:
        if not self.decision:
            return {"message": "Decision engine offline.", "type": "error"}
        result = await self.decision.handle_memory_query(cmd)
        return {"message": result.get("message", "No memories found."),
                "type": "memory_result", "phase2_data": result}

    # ── Background RNN Retraining ──────────────────────────────────────────────
    async def _rnn_retrain_loop(self, interval_minutes: int = 60):
        while True:
            await asyncio.sleep(interval_minutes * 60)
            try:
                if self.rnn:
                    stats = self.rnn.get_stats()
                    if stats.get("total_events", 0) >= 50:
                        logger.info("[Phase2] Auto-retraining RNN...")
                        result = await self.rnn.train_on_history(epochs=20)
                        logger.info(f"[Phase2] RNN retrain: {result.get('best_loss', '?')}")
            except Exception as e:
                logger.error(f"[Phase2] RNN retrain error: {e}")

    # ── Public API ─────────────────────────────────────────────────────────────
    def log_command(self, command: str, success: bool, latency_ms: float = 0, model_used: str = ""):
        if self.self_learn:
            self.self_learn.log_interaction(command=command, success=success,
                                            latency_ms=latency_ms, model_used=model_used)
        if self.rnn:
            self.rnn.record_command(command)

    async def get_proactive_hints(self) -> List[Dict]:
        if not self.decision:
            return []
        return await self.decision.get_proactive_suggestions()

    def store_memory(self, text: str, category: str = "general"):
        if self.memory:
            self.memory.store_text(text, category=category)

    def get_status(self) -> Dict:
        status: Dict = {"ready": self._ready, "timestamp": datetime.now().isoformat()}
        if self.gpu:       status["gpu"]          = self.gpu.get_summary()
        if self.memory:    status["memory"]        = self.memory.get_memory_stats()
        if self.trainer:   status["training"]      = self.trainer.get_status()
        if self.rnn:       status["rnn"]           = self.rnn.get_stats()
        if self.self_learn:status["self_learning"] = self.self_learn.get_learning_summary()
        if self._bg_coord: status["bg_coordinator"]= self._bg_coord.get_status()
        status["cnn_available"] = self.cnn is not None
        return status

    async def shutdown(self):
        logger.info("[Phase2] Shutting down...")
        for task in [self._training_task, self._proactive_task, self._rnn_retrain_task]:
            if task and not task.done():
                task.cancel()
        if self.trainer and getattr(self.trainer, 'state', None) and self.trainer.state.is_training:
            self.trainer.stop_training()
        if self.cnn:       self.cnn.shutdown()
        if self.gpu:       self.gpu.shutdown()
        if self._bg_coord: self._bg_coord.stop()
        logger.info("[Phase2] Shutdown complete")
        self._publish("phase2.status", {"status": "stopped"})

    def _publish(self, topic: str, payload: dict):
        if getattr(self, "bus", None):
            self.bus.publish(topic, payload, source="phase2")
