"""
JARVIS Phase 2 — Multimodal Decision Engine
=============================================
Combines all modalities to make intelligent, context-aware decisions:
  - Voice (spoken commands / text input)
  - Screen (visible applications)
  - Camera (user presence, environment)
  - Memory (past interactions, preferences)
  - System state (CPU, RAM, GPU, battery)

Then selects the optimal action plan.

Examples:
  "I see VS Code open → suggest coding mode"
  "User absent from desk → pause notifications"
  "Low battery + gaming → alert user"
  "You usually open AI notes now → proactive suggestion"

Usage:
    from core.phase2.decision_engine import DecisionEngine
    engine = DecisionEngine(config, memory, cnn_engine, rnn_engine)
    decision = await engine.decide("open my project files")
    proactive = await engine.get_proactive_suggestions()
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("jarvis.phase2.decision_engine")

ROOT = Path(__file__).resolve().parent.parent.parent


# ─── Context Snapshot ────────────────────────────────────────────────────────────
class ContextSnapshot:
    """Point-in-time snapshot of the system's perceptual state."""

    def __init__(self):
        self.timestamp     = datetime.now().isoformat()
        self.user_command  = ""
        self.screen_info   = {}   # from CNN screen analysis
        self.camera_info   = {}   # from CNN presence detection
        self.system_info   = {}   # CPU/RAM/GPU/battery
        self.memory_context = ""  # from MultimodalMemory
        self.rnn_prediction = {}  # from BehaviorRNN
        self.active_windows = []  # visible applications
        self.mode          = "normal"  # normal/coding/gaming/away

    def to_dict(self) -> Dict:
        return {
            "timestamp":     self.timestamp,
            "user_command":  self.user_command,
            "screen":        self.screen_info,
            "camera":        self.camera_info,
            "system":        self.system_info,
            "rnn":           self.rnn_prediction,
            "windows":       self.active_windows[:5],
            "mode":          self.mode,
        }

    def as_llm_context(self) -> str:
        """Format snapshot as system context block for LLM."""
        parts = ["[MULTIMODAL CONTEXT]"]

        # Screen
        if self.screen_info.get("scene_summary"):
            parts.append(f"Screen: {self.screen_info['scene_summary']}")

        # Active apps
        wins = [w.get("Name", "") for w in self.active_windows if w.get("Name")]
        if wins:
            parts.append(f"Active apps: {', '.join(wins[:5])}")

        # User presence
        if self.camera_info:
            present = self.camera_info.get("present", None)
            if present is True:
                parts.append(f"User: present at desk ({self.camera_info.get('faces', 1)} face(s) detected)")
            elif present is False:
                parts.append("User: away from desk")

        # System health
        sys_info = self.system_info
        if sys_info:
            cpu  = sys_info.get("cpu_percent", "?")
            ram  = sys_info.get("ram_percent", "?")
            gpu  = sys_info.get("gpu_percent", "?")
            parts.append(f"System: CPU={cpu}% RAM={ram}% GPU={gpu}%")
            batt = sys_info.get("battery", None)
            if batt is not None:
                parts.append(f"Battery: {batt}%")

        # RNN prediction
        top_cmd = self.rnn_prediction.get("top_command")
        if top_cmd:
            conf = self.rnn_prediction.get("lstm_predictions", [{}])[0].get("confidence", 0) if self.rnn_prediction.get("lstm_predictions") else 0
            parts.append(f"Predicted next action: {top_cmd} (confidence={conf:.1%})")

        # Mode
        parts.append(f"Mode: {self.mode}")

        return "\n".join(parts)


# ─── Decision Engine ─────────────────────────────────────────────────────────────
class DecisionEngine:
    """
    Multimodal decision engine: fuses all sensory inputs to make
    intelligent decisions and generate proactive suggestions.
    """

    def __init__(
        self,
        config: dict = None,
        memory=None,
        cnn_engine=None,
        rnn_engine=None,
        behavior_learning=None,
        llm_client=None,
    ):
        self.config           = config or {}
        self.memory           = memory           # MultimodalMemory
        self.cnn              = cnn_engine        # CNNVisionEngine
        self.rnn              = rnn_engine        # BehaviorRNN
        self.self_learn       = behavior_learning # SelfImprovementEngine
        self.llm              = llm_client        # LLM client

        self._last_context: Optional[ContextSnapshot] = None
        self._mode            = "normal"
        self._last_presence   = True
        self._proactive_cache: List[Dict] = []

    # ── System Snapshot ────────────────────────────────────────────────────────
    def _get_system_info(self) -> Dict:
        info = {}
        try:
            import psutil
            cpu  = psutil.cpu_percent(interval=0.1)
            ram  = psutil.virtual_memory()
            info["cpu_percent"] = round(cpu, 1)
            info["ram_percent"] = round(ram.percent, 1)
            info["ram_total_gb"] = round(ram.total / 1e9, 1)

            # Battery
            batt = psutil.sensors_battery()
            if batt:
                info["battery"] = round(batt.percent, 1)
                info["plugged"]  = batt.power_plugged
        except ImportError:
            pass

        # GPU via pynvml
        try:
            import pynvml
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            u = pynvml.nvmlDeviceGetUtilizationRates(h)
            m = pynvml.nvmlDeviceGetMemoryInfo(h)
            info["gpu_percent"]  = u.gpu
            info["vram_used_mb"] = round(m.used / 1e6, 0)
            info["vram_total_mb"] = round(m.total / 1e6, 0)
        except Exception:
            info["gpu_percent"] = "N/A"

        return info

    def _detect_mode(self, snapshot: ContextSnapshot) -> str:
        """Determine current operating mode from context."""
        apps  = [w.get("Name", "").lower() for w in snapshot.active_windows]
        titles = [w.get("title", "").lower() for w in snapshot.active_windows]

        if any(a in ("code", "pycharm", "cursor", "vim", "notepad++") for a in apps):
            return "coding"
        if any("game" in t or "steam" in t for t in titles) or "steam" in apps:
            return "gaming"
        if not snapshot.camera_info.get("present", True):
            return "away"
        if any("youtube" in t or "netflix" in t or "vlc" in t for t in titles):
            return "media"

        return "normal"

    # ── Full Context Gathering ─────────────────────────────────────────────────
    async def gather_context(
        self,
        command: str = "",
        use_camera: bool = False,
        use_screen: bool = True,
    ) -> ContextSnapshot:
        """
        Gather all perceptual inputs into a unified ContextSnapshot.
        This is the main "perception" step before decision making.
        """
        snapshot              = ContextSnapshot()
        snapshot.user_command = command

        # System info (fast, sync)
        snapshot.system_info  = self._get_system_info()

        tasks = []

        # Screen analysis (async)
        if use_screen and self.cnn:
            tasks.append(("screen", self.cnn.analyze_screen(classify=True, detect=False)))

        # Camera (async, optional)
        if use_camera and self.cnn:
            tasks.append(("camera", self.cnn.detect_user_presence()))

        # Active windows (async)
        if self.cnn:
            tasks.append(("windows", self.cnn.identify_active_application()))

        # Execute all async tasks concurrently
        if tasks:
            results = await asyncio.gather(
                *[coro for _, coro in tasks],
                return_exceptions=True,
            )
            for (key, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    logger.warning(f"[Decision] Context gather {key} failed: {result}")
                else:
                    if key == "screen":
                        snapshot.screen_info = result
                    elif key == "camera":
                        snapshot.camera_info = result
                    elif key == "windows":
                        snapshot.active_windows = result.get("windows", [])

        # RNN prediction
        if self.rnn:
            try:
                snapshot.rnn_prediction = self.rnn.predict_now()
            except Exception as e:
                logger.warning(f"[Decision] RNN prediction failed: {e}")

        # Memory context
        if self.memory and command:
            try:
                snapshot.memory_context = self.memory.get_relevant_context(command)
            except Exception as e:
                logger.warning(f"[Decision] Memory retrieval failed: {e}")

        # Detect mode
        snapshot.mode = self._detect_mode(snapshot)
        self._mode    = snapshot.mode

        self._last_context = snapshot
        return snapshot

    # ── Model Routing ─────────────────────────────────────────────────────────
    def route_command(self, command: str, snapshot: ContextSnapshot) -> Dict:
        """
        Decide which subsystem should handle the command.
        Returns routing decision dict.
        """
        cmd = command.lower().strip()

        # Vision-related
        if any(w in cmd for w in [
            "classify", "detect", "identify", "what do you see",
            "analyze screen", "describe screen", "look at", "camera", "photo", "take picture"
        ]):
            return {"handler": "cnn", "reason": "vision_command", "priority": "high"}

        # Training-related
        if any(w in cmd for w in [
            "train", "collect dataset", "start training", "stop training",
            "training progress", "dataset"
        ]):
            return {"handler": "vision_trainer", "reason": "training_command", "priority": "normal"}

        # Behavior/prediction
        if any(w in cmd for w in [
            "predict", "what will i do", "routine", "pattern",
            "suggest", "what usually", "next action"
        ]):
            return {"handler": "rnn", "reason": "prediction_command", "priority": "normal"}

        # System automation
        if any(w in cmd for w in [
            "open ", "launch", "close ", "shutdown", "restart",
            "volume", "brightness", "sleep", "lock"
        ]):
            return {"handler": "automation", "reason": "system_command", "priority": "high"}

        # Coding
        if any(w in cmd for w in [
            "code", "write function", "debug", "fix error",
            "implement", "python", "javascript"
        ]) or snapshot.mode == "coding":
            return {"handler": "coder_llm", "reason": "coding_context", "priority": "normal"}

        # Memory queries
        if any(w in cmd for w in [
            "remember", "recall", "what did i", "memory", "history",
            "last time", "previously"
        ]):
            return {"handler": "memory_search", "reason": "memory_query", "priority": "normal"}

        # Default: LLM reasoning
        # Use self-learning suggestion if available
        if self.self_learn:
            suggestion = self.self_learn.suggest_model(command)
            if suggestion.get("confidence", 0) > 0.7:
                return {
                    "handler":    suggestion["model"],
                    "reason":     f"learned_{suggestion['reason']}",
                    "priority":   "normal",
                    "confidence": suggestion["confidence"],
                }

        return {"handler": "llm", "reason": "default_reasoning", "priority": "normal"}

    # ── Main Decision Flow ─────────────────────────────────────────────────────
    async def decide(
        self,
        command: str,
        use_camera: bool = False,
        use_screen: bool = False,
    ) -> Dict:
        """
        Main decision-making entry point.
        Gathers context → routes command → returns decision package.

        Args:
            command:     User command or query
            use_camera:  Whether to capture a webcam frame for context
            use_screen:  Whether to analyze the screen

        Returns:
            dict with routing, context summary, suggestions, proactive hints
        """
        snapshot = await self.gather_context(command, use_camera, use_screen)
        routing  = self.route_command(command, snapshot)

        # Build proactive hints
        hints = self._generate_hints(snapshot)

        # Record in behavior learning
        if self.self_learn and command:
            self.self_learn.log_interaction(
                command     = command,
                model_used  = routing["handler"],
                success     = True,
            )

        if self.rnn and command:
            self.rnn.record_command(command)

        if self.memory and command:
            self.memory.store_text(
                f"User command: {command}",
                category="conversation",
                importance=0.8,
            )

        return {
            "command":        command,
            "routing":        routing,
            "context":        snapshot.to_dict(),
            "llm_context":    snapshot.as_llm_context(),
            "memory_context": snapshot.memory_context,
            "proactive_hints": hints,
            "mode":           snapshot.mode,
            "timestamp":      snapshot.timestamp,
        }

    # ── Proactive Suggestions ──────────────────────────────────────────────────
    def _generate_hints(self, snapshot: ContextSnapshot) -> List[Dict]:
        """Generate proactive suggestions based on context."""
        hints = []

        # Presence transition
        currently_present = snapshot.camera_info.get("present", True)
        if not currently_present and self._last_presence:
            hints.append({
                "type":    "presence",
                "message": "You've stepped away. Pausing non-critical processes.",
                "action":  "pause_notifications",
            })
        self._last_presence = currently_present

        # Low battery warning
        batt = snapshot.system_info.get("battery")
        plugged = snapshot.system_info.get("plugged", True)
        if batt is not None and not plugged and batt < 20:
            hints.append({
                "type":    "battery_warning",
                "message": f"Battery at {batt:.0f}%. Please plug in your charger.",
                "action":  "alert_battery",
                "urgency": "high" if batt < 10 else "normal",
            })

        # Gaming + high GPU
        gpu = snapshot.system_info.get("gpu_percent", 0)
        if snapshot.mode == "gaming" and isinstance(gpu, int) and gpu > 90:
            hints.append({
                "type":    "performance",
                "message": f"GPU at {gpu}%. Consider closing background apps for better performance.",
                "action":  "optimize_gaming",
            })

        # Mode transition suggestions
        if snapshot.mode == "coding":
            hints.append({
                "type":    "mode",
                "message": "Coding mode active. DeepSeek Coder ready for assistance.",
                "action":  "activate_coding_mode",
            })

        # RNN prediction hint
        top_cmd = snapshot.rnn_prediction.get("top_command")
        if top_cmd and top_cmd not in ("", None):
            hints.append({
                "type":    "prediction",
                "message": f"Based on your routine, you might want to: {top_cmd.replace('_', ' ')}",
                "action":  f"suggest:{top_cmd}",
            })

        # Time-based hints
        hour = datetime.now().hour
        if 12 <= hour <= 14:
            hints.append({
                "type":    "routine",
                "message": "It's lunchtime. You usually take a break around now.",
                "action":  "lunch_reminder",
            })
        elif 22 <= hour or hour < 6:
            hints.append({
                "type":    "routine",
                "message": "Working late. Remember to rest — JARVIS can continue in background.",
                "action":  "sleep_reminder",
            })

        return hints

    async def get_proactive_suggestions(self, use_camera: bool = False) -> List[Dict]:
        """
        Called periodically to check if JARVIS should say/do something
        without being asked. Returns list of suggestion dicts.
        """
        snapshot = await self.gather_context("", use_camera=use_camera, use_screen=False)
        hints    = self._generate_hints(snapshot)

        # Self-learning suggestions
        if self.self_learn:
            sl_suggestions = self.self_learn.get_suggestions()
            hints.extend(sl_suggestions[:2])  # limit to 2

        return hints

    # ── Memory Query Handler ───────────────────────────────────────────────────
    async def handle_memory_query(self, query: str) -> Dict:
        """
        Handle a memory search query and return formatted results.
        """
        if not self.memory:
            return {"error": "Memory system not initialized"}

        results = self.memory.search(query, top_k=5)
        if not results:
            return {
                "message": "I don't have specific memories about that.",
                "results": [],
            }

        lines = []
        for r in results:
            ts = r.get("timestamp", "")[:16]
            c  = r.get("content", r.get("description", ""))
            lines.append(f"• [{ts}] {c[:120]}")

        return {
            "message": "Here's what I remember:\n" + "\n".join(lines),
            "results": results,
            "count":   len(results),
        }

    # ── Status ─────────────────────────────────────────────────────────────────
    def get_status(self) -> Dict:
        """Current engine status and last context summary."""
        ctx = self._last_context
        return {
            "mode":               self._mode,
            "last_context_time":  ctx.timestamp if ctx else None,
            "cnn_available":      self.cnn is not None,
            "rnn_available":      self.rnn is not None,
            "memory_available":   self.memory is not None,
            "llm_available":      self.llm is not None,
        }
