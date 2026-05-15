"""
JARVIS Configuration & Path Manager
Handles all path resolution for Windows/Linux/Mac.
Import this first in every module.
"""

import json
import logging
import os
import sys
from copy import deepcopy
from pathlib import Path

# ── Resolve project root no matter where you run from ──────────────────────
ROOT = Path(__file__).resolve().parent.parent  # jarvis_v3/
sys.path.insert(0, str(ROOT))

LOG_DIR = ROOT / "logs"
DB_DIR  = ROOT / "database"
SS_DIR  = ROOT / "screenshots"
CFG_DIR = ROOT / "config"

for d in [LOG_DIR, DB_DIR, SS_DIR, CFG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Logging (call setup_logging() once at entry point) ─────────────────────
def setup_logging(name: str = "jarvis") -> logging.Logger:
    try:
        from core.logger import setup_runtime_logging
        return setup_runtime_logging(name)
    except Exception:
        # Force UTF-8 on Windows to avoid cp1252 crashes
        import sys, io
        if sys.platform == "win32":
            try:
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
            except Exception:
                pass

        fmt = logging.Formatter("%(asctime)s [%(name)-20s] %(levelname)s: %(message)s")
        log_file = LOG_DIR / "jarvis.log"

        handlers = [logging.StreamHandler(sys.stdout)]
        try:
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except Exception:
            pass

        for h in handlers:
            h.setFormatter(fmt)

        root = logging.getLogger()
        root.setLevel(logging.INFO)
        if not root.handlers:
            for h in handlers:
                root.addHandler(h)

        return logging.getLogger(name)


# ── Config loading ──────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "llm": {
        "provider": "ollama",
        "model":    "llama3.2",
        "api_key":  "",
        "max_tokens": 2048,
        "ollama_url": "http://localhost:11434",
        "fallback_model": "mistral",
        "coder_model": "deepseek-coder",
    },
    "voice": {
        "tts_backend": "piper",
        "stt_model":   "base",            # whisper model size
        "language":    "auto",
        "wake_word":   "jarvis",
    },
    "memory": {
        "db_path":    str(DB_DIR / "memory.db"),
        "chroma_path": str(DB_DIR / "chroma"),
    },
    "android": {
        "device_id": None,
        "adb_path":  "adb",
    },
    "learning": {
        "interval_minutes": 30,
        "min_samples": 5,
    },
    "always_ask_for": ["delete_file", "send_email", "purchase", "system_command"],
    "permission_overrides": {},
    "vision": {
        "gpu": True,
    },
    "sandbox": {
        "root": "sandbox",
        "keep_failed_sessions": True,
        "default_timeout_seconds": 20,
    },
    "reliability": {
        "max_retries": 2,
        "retry_backoff_ms": 250,
        "minimum_plan_confidence": 0.5,
    },
    "evolution": {
        "enabled": True,
        "experimental_mode": False,
        "plugin_auto_deploy": False,
        "protected_boot_files": [
            "main.py",
            "jarvis_gui.py",
            "core/config.py",
            "core/updater.py",
            "core/upgrade_engine.py",
            "core/safety.py",
            "core/permission_engine.py",
            "agents/agent_registry.py",
        ],
    },
}


def load_config() -> dict:
    cfg_path = CFG_DIR / "config.json"
    config = deepcopy(DEFAULT_CONFIG)

    if cfg_path.exists():
        try:
            with open(cfg_path, encoding="utf-8") as f:
                user = json.load(f)
            # Deep merge
            for key, val in user.items():
                if isinstance(val, dict) and key in config:
                    config[key].update(val)
                else:
                    config[key] = val
        except Exception as e:
            print(f"[config] Warning: could not load config.json: {e}")

    # Fill API key from environment if not set
    if not config["llm"]["api_key"]:
        config["llm"]["api_key"] = (
            os.environ.get("ANTHROPIC_API_KEY") or
            os.environ.get("OPENAI_API_KEY") or ""
        )

    return config


def save_config(config: dict):
    cfg_path = CFG_DIR / "config.json"
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
