"""
JARVIS API Server — FastAPI bridge for the Electron UI.
Run: python api_server.py --port 7474
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# ── Fix imports regardless of working directory ──────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.config import load_config, setup_logging

log = setup_logging("jarvis.api")

try:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    print("ERROR: Install FastAPI: pip install fastapi uvicorn")
    sys.exit(1)

app = FastAPI(title="JARVIS API v3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_orch = None   # JARVISOrchestrator instance


# ── Models ───────────────────────────────────────────────────────────────────
class ProcessReq(BaseModel):
    input: str
    context: dict = {}

class ConfirmReq(BaseModel):
    task_id: str
    confirmed: bool

class StopReq(BaseModel):
    task_id: str = ""


# ── Startup ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_start():
    global _orch, _va
    config = load_config()
    from core.orchestrator import JARVISOrchestrator
    from agents.voice_agent import VoiceAgent
    _orch = JARVISOrchestrator(config)
    _va    = VoiceAgent(config)
    print("JARVIS API ready", flush=True)   # ← Electron looks for this exact string
    log.info("JARVIS API server ready.")
    asyncio.create_task(_warm_llm_models())


# ── Endpoints ────────────────────────────────────────────────────────────────
@app.post("/process")
async def process(req: ProcessReq):
    if not _orch:
        return {"type": "error", "message": "Orchestrator not ready. Please wait."}
    try:
        # Handle voice trigger
        if req.input == "__START_VOICE__":
            return await _do_voice()
        if req.input == "__STOP_VOICE__":
            return {"type": "success", "message": "Voice stopped."}

        result = await _orch.process(req.input, context=req.context)
        # Normalize type field so Electron widget handles it correctly
        if result.get("type") == "confirmation_required":
            result["type_inner"] = "confirmation_required"
        
        log.info(f"Response generated for '{req.input[:30]}...': {result.get('type')}")
        return result
    except Exception as e:
        log.error(f"/process error: {e}", exc_info=True)
        return {"type": "error", "message": f"Error: {e}"}


@app.post("/confirm")
async def confirm(req: ConfirmReq):
    if not _orch:
        return {"type": "error", "message": "Not ready"}
    try:
        return await _orch.confirm_task(req.task_id, req.confirmed)
    except Exception as e:
        return {"type": "error", "message": str(e)}


@app.post("/stop")
async def stop(req: StopReq):
    if _orch and req.task_id:
        await _orch.stop_task(req.task_id)
    return {"status": "stopped"}


@app.post("/status")
async def status(_: dict = {}):
    """System health for dashboard metrics."""
    cpu = ram = 0
    try:
        import psutil
        cpu = round(psutil.cpu_percent(interval=0.1), 1)
        ram = round(psutil.virtual_memory().percent, 1)
    except ImportError:
        pass

    memories = 0
    tasks = 0
    llm_ready = False
    voice_ready = bool(_va)
    if _orch:
        try:
            memories = _orch.memory.get_interaction_count()
            tasks    = len(_orch._tasks)
            llm_ready = _orch.llm.is_ollama_running()
        except Exception:
            llm_ready = True

    return {
        "llm_ready":    llm_ready or bool(_orch),
        "memory_ready": bool(_orch),
        "voice_ready":  voice_ready,
        "cpu":    cpu,
        "ram":    ram,
        "tasks":  tasks,
        "memories": memories,
    }


async def _do_voice() -> dict:
    """Trigger microphone listen → transcribe → process."""
    if not _orch or not _va:
        return {"type": "error", "message": "Not ready"}
    try:
        result = await _va.listen(timeout=10)
        text   = result.get("text", "").strip()
        if not text:
            detail = result.get("error", "Didn't catch that. Please try again.")
            return {"type": "error", "message": f"Voice error: {detail}"}
        log.info(f"Voice transcribed: {text}")
        return await _orch.process(text, context={"mode": "voice"})
    except Exception as e:
        return {"type": "error", "message": f"Voice error: {e}"}


# ── Entry point ───────────────────────────────────────────────────────────────
async def _warm_llm_models():
    if not _orch:
        return
    try:
        warmed = await _orch.router.warm_models_async(["phi", "mistral"])
        if warmed:
            log.info(f"[OK] Warmed models: {', '.join(warmed)}")
    except Exception as e:
        log.debug(f"LLM warm-up skipped: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7474)
    args = parser.parse_args()

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
