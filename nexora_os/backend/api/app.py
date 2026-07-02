from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..core.runtime import NexoraRuntime, configure_logging

ROOT = Path(__file__).resolve().parents[2]
configure_logging(ROOT)
runtime = NexoraRuntime(ROOT)
app = FastAPI(title="NEXORA OS API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ProcessRequest(BaseModel):
    input: str
    context: dict[str, Any] = Field(default_factory=dict)


class SpeakRequest(BaseModel):
    text: str
    interrupt: bool = True


class MemoryRequest(BaseModel):
    text: str
    memory_type: str = "semantic"
    tags: list[str] = Field(default_factory=list)


class GraphRequest(BaseModel):
    name: str
    description: str = ""
    graph: dict[str, Any]
    enabled: bool = True
    schedule_seconds: int = 0
    retries: int = 2


class DescriptionRequest(BaseModel):
    description: str


class AgentBuildRequest(BaseModel):
    description: str
    name: str = ""


class AgentTaskRequest(BaseModel):
    task: dict[str, Any] = Field(default_factory=dict)


@app.on_event("startup")
async def startup() -> None:
    await runtime.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await runtime.shutdown()


@app.get("/status")
async def status() -> dict[str, Any]:
    snap = runtime.monitor.snapshot()
    return {
        "llm_ready": runtime.llm.ready(),
        "voice_ready": runtime.voice.health()["stt_available"] or runtime.voice.health()["tts_available"],
        "memory_ready": True,
        "voice_state": runtime.voice.state,
        "cpu": snap["cpu_percent"],
        "ram": snap["memory_percent"],
        "gpu": snap["gpu"],
        "tasks": sum(row["queued"] for row in snap["agents"]),
        "memories": runtime.memory.count(),
        "modules": len(snap["modules"]),
        "event_errors": snap["event_bus"]["subscriber_error_count"],
        "events_per_sec": snap["event_bus"]["events_per_sec"],
        "active_agents": snap["active_agents"],
        "active_workflows": snap["active_workflows"],
        "process_memory_mb": snap["process_memory_mb"],
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    snapshot = runtime.monitor.snapshot()
    startup = runtime.monitor.startup_verification()
    return {"ok": all(row["status"] == "online" for row in snapshot["modules"]) and startup["ok"], "startup": startup, "snapshot": snapshot}


@app.get("/state")
async def state() -> dict[str, Any]:
    return runtime.bus.state_snapshot()


@app.get("/events")
async def events(limit: int = 80) -> dict[str, Any]:
    return {"events": runtime.bus.history(min(limit, 200))}


@app.get("/agents")
async def agents() -> dict[str, Any]:
    rows = runtime.agents.health()
    return {"tool_agents": rows, "runtime_agents": rows}


@app.get("/tools")
async def tools() -> dict[str, Any]:
    return {"tools": runtime.automation.status()["registered_actions"]}


@app.post("/nlp/process")
async def nlp_process(request: ProcessRequest) -> dict[str, Any]:
    text = request.input.strip()
    language = runtime.voice.language(text)
    return {
        "type": "success",
        "message": "NLP route resolved.",
        "nlp": {
            "text": text,
            "language": language,
            "uses_llm": text.lower().startswith(("ask ", "llm ")),
        },
    }


@app.post("/agents/{name}/tasks")
async def agent_task(name: str, request: AgentTaskRequest) -> dict[str, Any]:
    return await runtime.agents.submit(name, request.task)


@app.post("/agents/build")
async def build_agent(request: AgentBuildRequest) -> dict[str, Any]:
    return runtime.creator.create(request.description, request.name)


@app.get("/agents/generated")
async def generated_agents() -> dict[str, Any]:
    return {"agents": runtime.creator.list()}


@app.get("/workflows")
async def workflows() -> dict[str, Any]:
    return {"workflows": runtime.workflows.list()}


@app.get("/workflows/graphs")
async def workflow_graphs() -> dict[str, Any]:
    return {"graphs": runtime.workflows.list()}


@app.get("/workflows/graph/{name}")
async def workflow_graph(name: str) -> dict[str, Any]:
    return runtime.workflows.get(name) or {"error": "Not found"}


@app.post("/workflows/graph/save")
async def workflow_save(request: GraphRequest) -> dict[str, Any]:
    return runtime.workflows.save(request.model_dump())


@app.post("/workflows/graph/run/{name}")
async def workflow_run(name: str) -> dict[str, Any]:
    return await runtime.workflows.run(name)


@app.post("/workflows/generate")
async def workflow_generate(request: DescriptionRequest) -> dict[str, Any]:
    result = runtime.workflows.generate(request.description)
    runtime.workflows.save(result["spec"])
    return result


@app.get("/workflows/trace/{name}")
async def workflow_trace(name: str, run_id: str | None = None) -> dict[str, Any]:
    return {"trace": runtime.workflows.trace(name, run_id)}


@app.get("/platform/node-types")
async def node_types() -> dict[str, Any]:
    return {"node_types": sorted(runtime.workflows.NODE_TYPES)}


@app.get("/memory")
async def memory(query: str = "", limit: int = 8) -> dict[str, Any]:
    return {"count": runtime.memory.count(), "items": runtime.memory.search(query, limit)}


@app.post("/memory/store")
async def memory_store(request: MemoryRequest) -> dict[str, Any]:
    return runtime.memory.store(request.text, request.memory_type, request.tags)


@app.get("/memory/search")
async def memory_search(q: str, limit: int = 10) -> dict[str, Any]:
    return {"items": runtime.memory.search(q, limit)}


@app.get("/memory/network")
async def memory_network() -> dict[str, Any]:
    return runtime.memory.network()


@app.post("/memory/reflect")
async def memory_reflect(query: str = "") -> dict[str, Any]:
    return runtime.memory.reflect(query)


@app.post("/process")
async def process(request: ProcessRequest) -> dict[str, Any]:
    return await runtime.process(request.input, request.context)


@app.post("/confirm")
async def confirm() -> dict[str, Any]:
    return {"type": "success", "message": "No pending confirmation."}


@app.post("/voice/listen")
async def voice_listen(timeout: float = 12) -> dict[str, Any]:
    return await runtime.agents.submit("VoiceAgent", {"action": "listen", "timeout": timeout})


@app.post("/voice/speak")
async def voice_speak(request: SpeakRequest) -> dict[str, Any]:
    return await runtime.agents.submit("VoiceAgent", {"action": "speak", "text": request.text})


@app.get("/voice/status")
async def voice_status() -> dict[str, Any]:
    return runtime.voice.health()


@app.post("/vision/webcam/start")
async def vision_start() -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "start"})


@app.post("/vision/webcam/stop")
async def vision_stop() -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "stop"})


@app.post("/vision/capture")
async def vision_capture() -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "capture"})


@app.post("/vision/frame")
async def vision_get_frame() -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "get_frame"})


@app.post("/vision/frame/mouse")
async def vision_get_frame_mouse() -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "get_frame_with_mouse"})


@app.post("/vision/mouse/enable")
async def vision_enable_mouse() -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "enable_mouse_control"})


@app.post("/vision/mouse/disable")
async def vision_disable_mouse() -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "disable_mouse_control"})


@app.get("/vision/mouse/state")
async def vision_mouse_state() -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "mouse_state"})


@app.post("/vision/screen")
async def vision_screen(ocr: bool = True) -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "screen", "ocr": ocr})


@app.get("/vision/status")
async def vision_status() -> dict[str, Any]:
    return runtime.vision.health()


@app.post("/vision/gestures/enable")
async def vision_enable_gestures() -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "enable_gestures"})


@app.post("/vision/gestures/disable")
async def vision_disable_gestures() -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "disable_gestures"})


@app.post("/vision/gestures/capture")
async def vision_capture_gestures() -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "capture_gestures"})


@app.get("/vision/gestures/state")
async def vision_gesture_state() -> dict[str, Any]:
    return await runtime.agents.submit("VisionAgent", {"action": "gesture_state"})


@app.get("/automation")
async def automation_status() -> dict[str, Any]:
    return runtime.automation.status()


@app.post("/automation/run")
async def automation_run(request: ProcessRequest) -> dict[str, Any]:
    return await runtime.automation.execute(request.input)


@app.get("/settings")
async def settings() -> dict[str, Any]:
    return {
        "api": {"host": "127.0.0.1", "port": 7474},
        "voice": runtime.voice.health(),
        "vision": runtime.vision.health(),
        "memory": {"database": str(runtime.memory.database), "chunks": runtime.memory.count()},
        "security": {"generated_code_execution": False, "agent_sandbox": str(runtime.creator.sandbox)},
        "llm": runtime.llm.status(),
    }


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def listener(event: Any) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    unsubscribe = runtime.bus.subscribe("*", listener)
    try:
        await websocket.send_json({"state": runtime.bus.state_snapshot(), "events": runtime.bus.history(30), "status": await status()})
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=2)
                outgoing = [event.__dict__ if hasattr(event, "__dict__") else {
                    "topic": event.topic, "payload": event.payload, "source": event.source,
                    "timestamp": event.timestamp, "sequence": event.sequence,
                    "priority": getattr(event, "priority", 1),
                }]
            except asyncio.TimeoutError:
                outgoing = []
            await websocket.send_json({"state": runtime.bus.state_snapshot(), "events": outgoing, "status": await status()})
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe()


def mount_frontend() -> None:
    dist = ROOT / "frontend" / "dist"
    if not dist.exists():
        return

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(dist / "index.html")

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7474)
    parser.add_argument("--serve-ui", action="store_true")
    args = parser.parse_args()
    if args.serve_ui:
        mount_frontend()
    uvicorn.run(app, host="127.0.0.1", port=args.port)
