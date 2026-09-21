# G / Nexora Recovery Test Report

Generated: 2026-09-21

## Commands Run This Pass

- `python -m pytest nexora_os/tests/test_tool_router.py nexora_os/tests/test_core_runtime.py nexora_os/tests/test_brain_block2.py nexora_os/tests/test_smoke.py -q`
  - Result: PASS
  - Output: `20 passed, 5 warnings`
  - Coverage:
    - capability-backed tool routing
    - core runtime regressions
    - brain block-2 regressions
    - API smoke tests including AI Lab agent creation policy

- `python nexora_os/tests/test_backend_modules.py`
  - Initial result: FAIL before module assertions because Windows console encoding `cp1252` could not print checkmark/cross symbols.
  - Failure class: `UnicodeEncodeError`, not a backend module failure.

- `$env:PYTHONIOENCODING='utf-8'; python nexora_os/tests/test_backend_modules.py`
  - Result: PASS
  - Output: `Passed: 24/24`, `Failed: 0/24`, `Success Rate: 100.0%`
  - Coverage:
    - VoiceEngine import/init/health
    - VisionEngine import/init/health
    - MemoryEngine import/init/store/search
    - AgentRuntime import/init
    - AutomationEngine import/init/status
    - WorkflowEngine import/init
    - AgentCreator import/init
    - FastAPI app import
    - SystemMonitor import
    - plugins/models/databases directory checks

- `python -m pytest nexora_os/tests/test_workflow_truthfulness.py nexora_os/tests/test_smoke.py -q`
  - Result: PASS
  - Output: `6 passed, 5 warnings`
  - Coverage:
    - unsupported/capability workflow nodes fail when no executor is registered
    - executor-backed workflow node output is preserved
    - workflow notifications publish real event-bus events
    - API smoke routes still respond

- `python -m pytest nexora_os/tests/test_frontend_api_contract.py -q`
  - Result: PASS
  - Output: `3 passed`
  - Coverage:
    - frontend pages do not hardcode the dev API origin
    - the central API client owns the `VITE_NEXORA_API` / dev-origin fallback
    - VisionPage uses `nexoraApi` for camera, OCR, screen, gesture, and mouse-control actions

- `python -m pytest nexora_os/tests/test_event_bus_recovery.py -q`
  - Result: PASS
  - Output: `3 passed`
  - Coverage:
    - pre-loop publication does not disable later async delivery
    - bounded async queue overflow increments dropped-event metrics without loop errors
    - async delivery can restart after shutdown

- `$env:PYTHONIOENCODING='utf-8'; python nexora_os/tests/test_core_runtime.py`
  - Result: PASS
  - Output: `Passed: 11/11`, `Failed: 0/11`, `Success Rate: 100.0%`
  - Coverage:
    - event bus creation, publish/subscribe, thread safety, metrics, and state management
    - module registration
    - core logging
    - async runtime startup/shutdown/task tracking

- `python -m pytest nexora_os/tests/test_agent_contract.py nexora_os/tests/test_smoke.py -q`
  - Result: PASS
  - Output: `7 passed, 5 warnings`
  - Coverage:
    - real `PlannerAgent` class returns a bounded plan
    - `AgentRuntime` exposes exactly four active recovery agents
    - `AutonomousAgent`, `ResearchAgent`, and `CodingAgent` are inactive/unknown until proven
    - `/agents` API returns four unique runtime rows

- `$env:PYTHONIOENCODING='utf-8'; python nexora_os/tests/test_backend_modules.py`
  - Result: PASS
  - Output: `Passed: 24/24`, `Failed: 0/24`, `Success Rate: 100.0%`
  - Coverage:
    - backend module imports and initialization
    - `PlannerAgent` import through the agents runtime module

- `npm run build` from repository root
  - Result: EXPECTED NON-SUCCESS
  - Output: `Missing script: "build"`
  - Note: the active frontend package is `nexora_os/frontend`; root has no package build script.

- `$env:PYTHONIOENCODING='utf-8'; python nexora_os/tests/test_integration_workflow.py`
  - Result: PASS
  - Output: `Passed: 6/6`, `Failed: 0/6`, `Success Rate: 100.0%`
  - Coverage:
    - workflow engine initialization and health
    - workflow graph save/list/retrieval
    - executor-backed workflow execution without fake standalone `memory_save` success

- `npm run build` from `nexora_os/frontend`
  - Result: PASS
  - Output: Vite `6.3.5`, `2789 modules transformed`
  - Assets:
    - `dist/index.html`
    - `dist/assets/index-CjnHNFBO.css`
    - `dist/assets/index--C4BBwpU.js` (`344.65 kB`, gzip `111.09 kB`)
    - lazy page chunks including `WorkflowStudio-tZiSPNy4.js`, `PetGPage-DbyDJa9k.js`, `Scene3D-C-voSy76.js`, and per-lens page files
  - Warning: one lazy Three/R3F runtime chunk remains larger than 500 kB (`extends-CEiTbmSj.js`, `874.58 kB`, gzip `235.88 kB`), but the previous eagerly loaded single-app bundle has been split.

- `cmd /c create_pet_g_blender_model.cmd`
  - Result: expected non-success on this machine because Blender is unavailable.
  - Verified behavior: the project launcher calls the local Pet G runner and prints actionable guidance:
    - install with `winget install --id BlenderFoundation.Blender -e`
    - or pass `-BlenderPath "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"`

## What This Proves

- The rebuilt frontend currently compiles for production, with the shell and major lenses split into lazy chunks.
- The capability-based tool router, core runtime, brain block-2 behavior, and smoke API coverage pass together.
- AI Lab creation behavior is now test-covered through explicit policy instead of a vague disabled path.
- The backend module surface can import and initialize across the major subsystems when Windows output encoding is set correctly.
- Workflow execution no longer reports standalone capability-node success without a registered executor; executor-backed node outputs and notification events are regression-tested.
- Vision UI calls are routed through the central frontend API client instead of page-level localhost fetches.
- Event-bus async delivery tuple handling is fixed, bounded queue drops are accounted, and core runtime event tests pass.
- Agent runtime now exposes a real `PlannerAgent` and the tested four-agent recovery contract.
- Pet G has a reproducible Blender workflow and a repository-root launcher; the previous raw `blender` command failure is handled by project tooling.

## What This Does Not Prove

- It does not prove Blender output generation on this machine because Blender is not installed or not visible on PATH.
- It does not prove a fresh live backend session on port `7474` after the latest commits.
- It does not prove live Ollama/LLM readiness.
- It does not prove microphone/speaker voice I/O or camera hardware behavior.
- It does not prove full master-prompt completion; it is a verified rebuild slice.

## Current Warnings

- FastAPI `on_event` deprecation warnings remain.
- `pynvml` deprecation warning remains from the installed Torch/NVIDIA stack.
- Vite bundle-size warning remains for the lazy Three/R3F runtime chunk, not the main shell bundle.
- `PYTHONIOENCODING=utf-8` is required for the custom backend harness on this Windows console when printing Unicode status symbols.
