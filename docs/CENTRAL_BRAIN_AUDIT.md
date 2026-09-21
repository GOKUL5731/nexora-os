# Central Brain Audit

Audit date: 2026-07-10
Repository: `C:\Users\gokul\Downloads\jarvis_v3_complete`
Active source root: `nexora_os/`

## Executive Summary

The current project is a consolidated NEXORA/Jarvis-style platform with one React Command Center UI and one FastAPI backend. The project is not currently a unified Central Neural Brain. It has working runtime pieces, but orchestration is still command-routing plus agents/workflows/tools, with several success paths that do not prove real execution.

The most important findings:

- Identity drift: the requested Jarvis system currently exists as `nexora_os`, `NEXORA_*` launchers, and NEXORA branding.
- Core startup/shutdown works at a basic level, but async event delivery is broken in direct subscriber verification.
- The official UI builds and connects to many backend endpoints. Earlier VisionPage hardcoded localhost API calls have been replaced with the central API client; other UI capability backing still requires ongoing verification.
- There is no `backend/brain/` package, no cognitive loop, no persistent goal manager, no capability registry, no model router, no tool router, no verifier, and no reflection engine.
- Workflow execution now inspects executor return values and rejects capability nodes without a runtime executor; broader node-by-node side-effect verification is still incomplete.
- Agent runtime exposes two `AutonomousAgent` health rows and no real `PlannerAgent` class, while tests import `PlannerAgent` and fail collection.
- AI Lab agent generation is still exposed through `/agents/build`, and generated agent sandboxes exist.
- Webcam and screen OCR were verified working on this machine; object detection is disconnected because the YOLO file is in root `models/` while vision code looks under `nexora_os/models/`.
- TTS spoke successfully through `pyttsx3`; STT timed out because no speech was captured during the test window.

## Verified Commands

| Check | Result | Evidence |
| --- | --- | --- |
| Python compile | PASSED | `python -m compileall -q nexora_os\backend nexora_os\tests` |
| Smoke tests | PASSED | `2 passed, 6 warnings` |
| Full pytest collection | FAILED | `ImportError: cannot import name 'PlannerAgent'` |
| Frontend build | PASSED_WITH_WARNING | Vite built; JS chunk `529.20 kB` |
| Import cycle scan | PASSED | 56 Python files, 0 parse errors, 0 cycles found |
| Runtime startup | PASSED | startup verification `ok=True`, no required core modules missing |
| Runtime shutdown | PASSED | async runtime stopped after shutdown |
| Event delivery | FAILED | published test event did not reach direct subscriber |
| API routes | PARTIAL | common REST routes 200; route success does not prove deep capability |
| Ollama discovery | PASSED | HTTP `/api/tags` returned installed models including `llama3.2:1b`, `phi`, `deepseek-coder` |
| Direct `ollama list` | FAILED/TIMEOUT | command timed out after ~34 seconds |
| Memory store/retrieve | PASSED | marker stored and retrieved as top result |
| TTS speak | PASSED | `pyttsx3` returned `ok: true` |
| STT listen | FAILED/TIMEOUT | `Microphone listening timed out.` |
| Webcam frame | PASSED | `cv2.VideoCapture(0)` opened and saved `nexora_os\logs\captures\audit_camera_test.jpg` |
| Screen OCR | PASSED | screenshot captured and OCR returned 1035 chars |

## Subsystem Classification

| Subsystem | Classification | Notes |
| --- | --- | --- |
| Command Center UI | PARTIALLY WORKING | Builds and uses backend state, and VisionPage now uses the central API client; not all controls are fully proven against real capability side effects. |
| Native Windows wrapper | PARTIALLY WORKING | `desktop_app.py` wraps local web UI in PySide6. It is a desktop shell over web tech, not a fully native UI. |
| One-click launcher | PARTIALLY WORKING | Checks deps and launches app, but still uses NEXORA naming and external installers/downloads. |
| FastAPI API layer | WORKING | Core REST endpoints respond in TestClient. |
| WebSocket manager | PARTIALLY WORKING | Endpoint exists, but relies on event bus behavior that failed direct subscriber verification. |
| Event bus | BROKEN | Async delivery path enqueues a 3-item tuple but delivery loop unpacks 2 values, causing swallowed delivery failure. |
| Module manager | PARTIALLY WORKING | Registers status rows, but there is no lifecycle contract enforcement. |
| Logger | WORKING | File logging initializes and writes logs. |
| Async runtime | PARTIALLY WORKING | Tracks tasks created through it, but many background tasks are created directly outside it. |
| Health monitor | PARTIALLY WORKING | Reports CPU/RAM/GPU/modules/events; can report healthy while event delivery is broken. |
| Local LLM bridge | PARTIALLY WORKING | HTTP discovery works; `ollama list` timed out; no model routing categories exist. |
| Central Brain | MISSING | No `backend/brain` package or cognitive loop. |
| Goal manager | MISSING | No persistent goal state machine. |
| Context manager | MISSING | No unified context scoring/budgeting/compression. |
| Capability registry | MISSING | Capabilities are hardcoded in runtime branches and automation status. |
| Planner | BROKEN | `PlannerAgent` is not a real class; runtime maps it to `AutonomousAgent`. |
| Tool router | MISSING | No risk-aware tool selection layer. |
| Model router | MISSING | Ollama client chooses first/default model, not by task capability. |
| Verifier | MISSING | Workflow/API success often means no exception, not verified side effect. |
| Reflection engine | MISSING | Memory reflection is a simple category summary, not task learning. |
| Memory engine | PARTIALLY WORKING | Chunking, hashing embeddings, SQLite storage and retrieval work; no external/vector DB or retention policy. |
| Agent runtime | PARTIALLY WORKING | Queues and delegates exist; naming/PlannerAgent/test mismatches remain. |
| Voice engine | PARTIALLY WORKING | Language detection and TTS work; STT timed out in live test; no full Mic -> STT -> NLP -> LLM -> TTS proof. |
| Vision engine | PARTIALLY WORKING | Webcam, frame capture, screenshot, OCR work; object detection model path is disconnected. |
| Workflow engine | PARTIALLY WORKING | Stores/runs graphs, records traces, fails unsupported/capability nodes without an executor, and supports runtime executor outputs; full side-effect verification remains incomplete. |
| Automation engine | PARTIALLY WORKING | System status works; browser/app/file actions exist but lack permission policy and full verification. |
| AI Lab | DISCONNECTED/PLACEHOLDER | Agent generation endpoint and sandbox exist despite recovery instruction to stop creating agents. |
| Observability | PARTIALLY WORKING | Real CPU/RAM/GPU/event metrics exist, but no dedicated Observability page and event metrics are undermined by event bus bug. |
| Connectors | MISSING | No `backend/connectors/` architecture. |

## Duplicate And Obsolete Items

| Path | Classification | Reason |
| --- | --- | --- |
| `logs/` | DUPLICATE/OBSOLETE | Root logs duplicate `nexora_os/logs/`; contains old Jarvis/NEXORA runtime artifacts. |
| `databases/` | DUPLICATE/OBSOLETE | Root DBs duplicate `nexora_os/databases/`; includes test DBs and generated agent registry. |
| `models/yolov8n.pt` | DISCONNECTED ASSET | Needed by vision, but code searches `nexora_os/models/yolov8n.pt`. |
| `nexora_os/models/` | EMPTY REQUIRED FOLDER | Expected by vision code but empty. |
| `ai_lab_sandbox/` | EMPTY/OBSOLETE | Root sandbox directory remains. |
| `nexora_os/ai_lab_sandbox/` | OBSOLETE/ACTIVE GENERATED ARTIFACTS | Contains generated `SmokeReporterAgent` sandboxes. |
| `nexora_os/backend/communication/` | DEAD/EMPTY | Empty folder, no references found. |
| `nexora_os/plugins/` | EMPTY | Placeholder only. |
| `.pytest_cache/`, `nexora_os/.pytest_cache/`, `__pycache__/` | GENERATED | Should not be source-controlled. |
| `tools/rename_to_nexora.py` | OBSOLETE WORKFLOW | Rebrand script appears completed and contains no-op rename logic. |

## Broken Imports And Tests

- `nexora_os/tests/test_agent_communication.py` imports `PlannerAgent`, but `nexora_os/backend/agents/runtime.py` no longer defines it.
- Multiple test classes define `__init__`, so pytest warns that they are not collected as tests.
- No circular imports were found by the local AST import scan.

## Placeholder Or Fake Success Behavior

- `WorkflowEngine._execute_condition()` returns true "for demonstration".
- `WorkflowEngine.run()` now treats executor `ok: false` as node failure and rejects unsupported/capability nodes without an executor; full verification of every supported runtime node remains open.
- `NexoraRuntime._execute_node()` returns `{"ok": True}` for unknown workflow node types after publishing an event.
- `/confirm` always returns "No pending confirmation."
- `/nlp/process` reports route resolution only; it does not run a real NLP/LLM pipeline.
- `AutomationEngine._launch_app()` can return success after invoking `start` without verifying process/application state.
- `AutonomousAgent._execute_tool("write_file")` can write arbitrary files without central permission policy.

## Do Not Delete Yet

Do not delete duplicate logs, databases, generated sandboxes, or rebrand tools until cleanup verification is completed and documented in `docs/CLEANUP_REPORT.md`. Some files may be useful evidence or test data, but they should not be treated as production source.
