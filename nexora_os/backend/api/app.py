from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..core.runtime import NexoraRuntime, configure_logging

ROOT = Path(__file__).resolve().parents[2]
configure_logging(ROOT)
runtime = NexoraRuntime(ROOT)
app = FastAPI(title="NEXORA OS API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

LOCAL_CLIENTS = {"127.0.0.1", "::1", "localhost", "testclient"}

@app.middleware("http")
async def security_middleware(request: Request, call_next: Any) -> Response:
    client_ip = request.client.host if request.client else "127.0.0.1"
    
    # 1. Rate Limiting
    if runtime.security.is_rate_limited(client_ip):
        return JSONResponse(status_code=429, content={"error": "Too Many Requests"})
        
    # 2. Authentication (skip for local, frontend assets, health/status)
    path = request.url.path
    if client_ip not in LOCAL_CLIENTS and not path.startswith(("/assets", "/health", "/status", "/companion/pair")):
        api_key = request.headers.get("X-API-Key")
        if not api_key or not runtime.security.verify_api_key(api_key):
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    # 3. Process Request
    response = await call_next(request)
    
    # 4. Audit Logging (don't log static assets or frequent status polls to avoid spam)
    if not path.startswith(("/assets", "/health", "/status")):
        runtime.security.log_audit(
            ip_address=client_ip,
            endpoint=path,
            method=request.method,
            status_code=response.status_code,
            user_agent=request.headers.get("user-agent", "")
        )
        
    return response

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


class ValidateCodeRequest(BaseModel):
    code: str


class AgentTaskRequest(BaseModel):
    task: dict[str, Any] = Field(default_factory=dict)


class KnowledgeIndexRequest(BaseModel):
    domain: str
    title: str
    content: str
    source: str = "user provided"
    tags: list[str] = Field(default_factory=list)


class PerceptionRequest(BaseModel):
    type: str = "text"
    content: str = ""
    path: str = ""
    source: str = ""
    remember: bool = True


class LiveKitTokenRequest(BaseModel):
    room: str = "jarvis-ai"
    identity: str = "jarvis-user"
    name: str = "Jarvis User"
    ttl_seconds: int = 3600


class OrchestrationRequest(BaseModel):
    project_name: str
    root_path: str
    goal: str
    target_workers: list[str] = Field(default_factory=lambda: ["codex", "cursor", "antigravity"])


class EmergencyStopRequest(BaseModel):
    reason: str = "user_requested"


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


@app.get("/brain/status")
async def brain_status() -> dict[str, Any]:
    return runtime.brain.snapshot()


@app.get("/cognition/status")
async def cognition_status() -> dict[str, Any]:
    return runtime.cognition.status()


@app.get("/orchestration/projects")
async def orchestration_projects() -> dict[str, Any]:
    return runtime.orchestrator.snapshot()


@app.get("/orchestration/adapters")
async def orchestration_adapters() -> dict[str, Any]:
    return {"adapters": runtime.orchestrator.adapter_status()}


@app.get("/orchestration/projects/{project_id}")
async def orchestration_project(project_id: str) -> dict[str, Any]:
    project = runtime.orchestrator.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.post("/orchestration/projects")
async def orchestration_start(request: OrchestrationRequest) -> dict[str, Any]:
    if not request.target_workers:
        raise HTTPException(status_code=422, detail="At least one target worker is required")
    project_id = await runtime.orchestrator.start_project(
        request.project_name,
        request.root_path,
        request.goal,
        request.target_workers,
    )
    return runtime.orchestrator.get_project(project_id) or {"project_id": project_id}


@app.post("/cognition/perceive")
async def cognition_perceive(request: PerceptionRequest) -> dict[str, Any]:
    return runtime.cognition.perceive(request.model_dump(exclude={"remember"}), remember=request.remember)


@app.get("/capabilities")
async def capabilities() -> dict[str, Any]:
    return {
        "capabilities": runtime.capabilities.discover_capabilities(),
        "health": runtime.capabilities.health_check(),
    }


@app.get("/security/status")
async def security_status() -> dict[str, Any]:
    return {"emergency_stop": runtime.security.emergency_stop_active, "health": runtime.security.health()}


@app.post("/security/emergency-stop")
async def security_emergency_stop(request: EmergencyStopRequest) -> dict[str, Any]:
    return runtime.security.emergency_stop(request.reason)


@app.post("/security/emergency-stop/clear")
async def security_emergency_stop_clear() -> dict[str, Any]:
    return runtime.security.clear_emergency_stop()



@app.get("/knowledge")
async def knowledge_status() -> dict[str, Any]:
    return {"status": runtime.knowledge.status(), "domains": runtime.knowledge.domains()}


@app.post("/knowledge/learn/{domain}")
async def knowledge_learn(domain: str, web: bool = False) -> dict[str, Any]:
    """Learn a domain. Pass ?web=true to fetch real documentation from the web."""
    if web:
        return await asyncio.to_thread(runtime.knowledge.web_learn_domain, domain)
    return runtime.knowledge.learn_domain(domain)


@app.get("/knowledge/search")
async def knowledge_search(q: str, domain: str = "", limit: int = 8) -> dict[str, Any]:
    return {"items": runtime.knowledge.search(q, domain, limit)}


@app.get("/knowledge/graph")
async def knowledge_graph(node: str = "", limit: int = 200) -> dict[str, Any]:
    return runtime.knowledge.graph(node, limit)


@app.post("/knowledge/index")
async def knowledge_index(request: KnowledgeIndexRequest) -> dict[str, Any]:
    return runtime.knowledge.index_text(request.domain, request.title, request.content, request.source, request.tags)


# ─── Conversation Memory Routes ──────────────────────────────────────────────

@app.get("/conversation/sessions")
async def conversation_sessions() -> dict[str, Any]:
    return {"sessions": runtime.conversation.list_sessions(), "total_turns": runtime.conversation.count()}


@app.get("/conversation/{session_id}")
async def conversation_get(session_id: str, limit: int = 50) -> dict[str, Any]:
    return {"turns": runtime.conversation.get_session(session_id, limit)}


@app.delete("/conversation/{session_id}")
async def conversation_clear(session_id: str) -> dict[str, Any]:
    return runtime.conversation.clear_session(session_id)


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


@app.get("/connectors")
async def connectors() -> dict[str, Any]:
    registry = getattr(runtime, "connector_registry", None)
    if registry:
        manifest = registry.manifest()
        return {
            "connectors": [
                {"name": name, "health": info["health"], "capabilities": info["capabilities"]}
                for name, info in manifest.items()
            ],
            "available": len(registry.available_connectors()),
            "capability_list": registry.capabilities(),
        }
    manager = getattr(runtime, "connector_manager", None)
    if not manager:
        return {"connectors": [], "available": 0}
    health = manager.health_all()
    available = manager.list_available()
    return {
        "connectors": [
            {"name": name, "health": status, "capabilities": getattr(manager.get(name), "get_capabilities", lambda: [])()}
            for name, status in health.items()
        ],
        "available": len(available),
    }



@app.post("/connectors/{name}/execute")
async def connector_execute(name: str, request: ProcessRequest) -> dict[str, Any]:
    manager = getattr(runtime, "connector_manager", None)
    if not manager:
        raise HTTPException(status_code=503, detail="Connector manager not initialized")
    connector = manager.get(name)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector '{name}' not found")
    action = request.context.get("action", "")
    allowed, reason = runtime.security.execution_allowed(name, str(action))
    if not allowed:
        runtime.bus.publish("security.permission_denied", {"connector": name, "action": action, "reason": reason}, "security")
        raise HTTPException(status_code=423, detail=reason)
    params = {k: v for k, v in request.context.items() if k != "action"}
    execute_fn = getattr(connector, "execute", None)
    if not execute_fn:
        raise HTTPException(status_code=400, detail="Connector has no execute method")
    import asyncio as _asyncio
    if _asyncio.iscoroutinefunction(execute_fn):
        result = await execute_fn(action, params)
    else:
        result = execute_fn(action, params)
    return result


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
    """Generate, validate and register a new agent using the AI Lab."""
    if not runtime._config_bool("agent_creation_enabled", False):
        raise HTTPException(status_code=503, detail="Agent creation is disabled in recovery mode.")
    result = await asyncio.to_thread(runtime.creator.create, request.description, request.name)
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result)
    return result


@app.get("/agents/generated")
async def generated_agents() -> dict[str, Any]:
    return {"agents": runtime.creator.list()}


@app.get("/ai_lab/status")
async def ai_lab_status() -> dict[str, Any]:
    """Return AI Lab state: registered agents, LLM availability."""
    return runtime.creator.status()


@app.post("/ai_lab/validate")
async def ai_lab_validate(request: ValidateCodeRequest) -> dict[str, Any]:
    """AST-validate Python code against the AI Lab security policy."""
    return runtime.creator.validate(request.code)


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
        "security": {
            "generated_code_execution": False,
            "agent_creation_enabled": False,
            "agent_sandbox": str(runtime.creator.sandbox),
        },
        "llm": runtime.llm.status(),
        "realtime": {"livekit": runtime.livekit.status()},
    }


@app.get("/realtime/livekit/status")
async def livekit_status() -> dict[str, Any]:
    return runtime.livekit.status()


@app.post("/realtime/livekit/token")
async def livekit_token(request: LiveKitTokenRequest) -> dict[str, Any]:
    result = runtime.livekit.issue_token(
        room=request.room,
        identity=request.identity,
        name=request.name,
        ttl_seconds=request.ttl_seconds,
    )
    if not result["ok"]:
        raise HTTPException(status_code=503, detail=result)
    return result


# ─── iPhone Companion API Routes ──────────────────────────────────────────────

class CompanionPairRequest(BaseModel):
    device_id: str
    device_name: str
    platform: str = "iOS"


class CompanionSyncRequest(BaseModel):
    device_id: str
    token: str
    clipboard: str = ""
    location: dict[str, float] = Field(default_factory=dict)
    notifications: list[dict[str, Any]] = Field(default_factory=list)


@app.post("/companion/pair")
async def companion_pair(request: CompanionPairRequest) -> dict[str, Any]:
    """Secure pairing endpoint for iPhone Companion app."""
    return runtime.companion.pair_device(
        device_id=request.device_id,
        device_name=request.device_name,
        platform=request.platform,
    )


@app.get("/companion/status")
async def companion_status() -> dict[str, Any]:
    """Status of paired companion devices and sync state."""
    status_data = runtime.companion.status()
    status_data["desktop_status"] = await status()
    return status_data


@app.post("/companion/sync")
async def companion_sync(request: CompanionSyncRequest) -> dict[str, Any]:
    """Sync clipboard, location, and notification payload from iPhone companion."""
    if not runtime.companion.verify_token(request.device_id, request.token):
        raise HTTPException(status_code=401, detail="Invalid token for device")

    return runtime.companion.sync_data(
        device_id=request.device_id,
        clipboard=request.clipboard,
        location=request.location,
        notifications=request.notifications,
    )


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
    if getattr(app.state, "frontend_mounted", False):
        return

    dist = ROOT / "frontend" / "dist"
    if not dist.exists():
        return

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(dist / "index.html")

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    app.state.frontend_mounted = True

mount_frontend()


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7474)
    parser.add_argument("--serve-ui", action="store_true")
    args = parser.parse_args()
    if args.serve_ui:
        mount_frontend()
    uvicorn.run(app, host="127.0.0.1", port=args.port)

