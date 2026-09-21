# Broken Connections

Audit date: 2026-07-10

## Critical

### Event Bus Async Delivery Is Broken

Resolved 2026-09-21: `_delivery_loop()` now unpacks `(priority, sequence, event)`, async delivery defaults to opt-in, queue size is bounded, overflow increments `dropped_count`, duplicate subscribers are ignored, and shutdown resets delivery state.

Verified:

- `python -m pytest nexora_os/tests/test_event_bus_recovery.py -q` passed.
- `$env:PYTHONIOENCODING='utf-8'; python nexora_os/tests/test_core_runtime.py` passed `11/11`.

Remaining risk:

- `/health` should still expose event-bus degradation when subscriber errors or drops rise; that is a health-monitor policy item, not the original delivery-loop crash.

### PlannerAgent Contract Is Broken

The runtime exposes a `PlannerAgent` key, but the instance is constructed as `AutonomousAgent("AutonomousAgent", ...)`. There is no exported `PlannerAgent` class.

Impact:

- `/agents` returns two rows both named `AutonomousAgent`.
- Tests fail importing `PlannerAgent`.
- UI cannot display a truthful PlannerAgent health row.

Evidence:

- Full pytest failed during collection: `ImportError: cannot import name 'PlannerAgent'`.
- Agent health returned two `AutonomousAgent` rows.

### Workflow Node Success Is Not Real Execution

The workflow engine accepts many node types, but the runtime executor only implements `memory_save`, `camera`/`ocr`, `agent_spawn`, and `wait`. Unknown node types publish `workflow.node` and return `ok: true`.

Impact:

- `voice_input -> llm -> memory_save` can report completed while `voice_input` and `llm` did nothing.
- Visual workflow state can show false completion.

Evidence:

- Audit workflow with `voice_input`, `llm`, and `memory_save` returned `ok: true`.
- Trace marked `voice_input` and `llm` completed in under 1 ms without STT or LLM side effects.

## High

### Central Brain Is Missing

No `backend/brain/` package or cognitive loop exists. Requests go through branch-based command routing in `NexoraRuntime.process()`.

Required but missing:

- cognitive core
- goal manager
- context manager
- planner
- capability registry
- model router
- tool router
- execution engine
- observation engine
- verifier
- reflection engine
- autonomy controller

### Object Detection Asset Path Is Disconnected

`VisionEngine._objects()` loads `Path(__file__).resolve().parents[2] / "models" / "yolov8n.pt"`, which resolves to `nexora_os/models/yolov8n.pt`. The actual model file exists at root `models/yolov8n.pt`.

Impact:

- Webcam capture can succeed while object detection silently returns `[]`.

### AI Lab Generator Still Exposed

`/agents/build` and `/agents/generated` remain active, and `runtime.creator` is initialized.

Impact:

- Recovery mode said stop creating agents.
- Generated agent sandboxes exist under `nexora_os/ai_lab_sandbox`.

### Vision UI Hardcodes Backend URL

Resolved 2026-09-21: `VisionPage.tsx` now uses the central `nexoraApi` client for camera frames, screen capture, OCR, gesture controls, and hand-mouse controls. Regression coverage in `nexora_os/tests/test_frontend_api_contract.py` prevents page-level hardcoded `http://127.0.0.1:7474` API calls from returning.

Remaining risk:

- The source-contract test proves the page routes through the central API client; it does not prove live camera hardware availability or object-detection quality.

### Confirmation API Is Placeholder

`POST /confirm` always returns success with "No pending confirmation."

Impact:

- UI has pending confirmation logic, but backend has no real confirmation state.

## Medium

### NLP Route Is Not A Real NLP Pipeline

`POST /nlp/process` returns language and `uses_llm` metadata but does not perform LLM understanding or intent execution.

### Module Lifecycle Contract Is Not Enforced

The prompt requires `initialize()`, `start()`, `health_check()`, `stop()`, `restart()`. Current modules are registered as status rows but do not share this contract.

### Async Runtime Is Bypassed

Agents, workflow scheduler, and event bus create tasks directly with `asyncio.create_task()` rather than through `AsyncRuntime`.

### Health Can Report OK While Core Event Delivery Is Degraded

The original async delivery crash is resolved, but `/health` still needs a clear degraded status policy when event-bus subscriber errors or dropped events increase.

### Automation Lacks Verification

App launch, browser open, and file operations can return success without independent verification and without a central permission/risk policy.

### Workflow Condition Nodes Are Demo Logic

`_execute_condition()` returns true for simple/expression conditions "for demonstration".

### Root Runtime Data Duplicates Package Runtime Data

Root `databases/`, `logs/`, and `models/` overlap with `nexora_os/databases`, `nexora_os/logs`, and `nexora_os/models`.

## Low

### FastAPI Startup Uses Deprecated Events

`@app.on_event("startup")` and `@app.on_event("shutdown")` produce deprecation warnings. This is not breaking today.

### Frontend Bundle Warning

Vite reports main JS chunk `529.20 kB`, above 500 kB warning threshold.

### Empty Folders

`nexora_os/backend/communication`, `nexora_os/plugins`, and `nexora_os/models` are empty.

### Mojibake In Some Source Strings

Some Tamil literals appear mojibaked in source and docs, likely from prior encoding damage. Unicode escape test for Tamil language detection passed.
