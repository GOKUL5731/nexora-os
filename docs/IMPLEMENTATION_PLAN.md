# Implementation Plan

Audit date: 2026-07-10

This plan follows the user instruction: audit and failure reproduction first, then stabilize existing systems before adding Central Brain features.

## Phase 0: Freeze Feature Expansion

Status: IN PROGRESS

- Do not create new agents.
- Do not create a second backend.
- Do not create another UI.
- Do not delete code until reference checks and tests are complete.
- Treat `nexora_os/frontend` as the current official Command Center UI.

## Phase 1: Stabilize Core Runtime

Priority: Critical

1. DONE: Fix `EventBus` async delivery tuple handling.
2. DONE: Add a bounded queue size and dropped-event accounting to event delivery.
3. Make subscriber exceptions visible through logs and health.
4. Ensure shutdown calls `EventBus.shutdown()`.
5. Stop creating background tasks outside `AsyncRuntime` where practical.
6. DONE/PARTIAL: Add lifecycle smoke tests for startup, event delivery, module registration, logging, and shutdown. Core runtime and event-bus recovery harnesses pass; full app lifecycle acceptance remains separate.
7. Update `/health` so event bus failure cannot report globally healthy.

Acceptance tests:

- Direct subscriber receives published event.
- WebSocket receives live published event.
- Runtime shutdown cancels agents/workflows/event bus tasks.
- `python -m pytest nexora_os/tests/test_core_runtime.py` is collectable and passes.

## Phase 2: Repair Agent Runtime

Priority: Critical

1. Restore a real `PlannerAgent` class or rename health rows/contracts honestly.
2. Remove duplicate `AutonomousAgent` health row.
3. Fix test imports or exports.
4. Keep only required active agents until Central Brain exists:
   - PlannerAgent
   - VoiceAgent
   - VisionAgent
   - WorkflowAgent
5. Disable `/agents/build` or gate it behind an explicit disabled/unavailable response during recovery.
6. Move generated sandboxes to cleanup only after tests confirm no runtime references.

Acceptance tests:

- `/agents` returns four unique active runtime agents.
- `ResearchAgent` and `CodingAgent` are either absent with documented disabled status or implemented and proven.
- Agent task result schema is consistent.

## Phase 3: Fix Workflow Truthfulness

Priority: Critical

1. DONE: Make `WorkflowEngine.run()` inspect executor return values.
2. DONE: Mark nodes failed when executor returns `ok: false`.
3. DONE: Explicitly reject unsupported/capability node types when no runtime executor is registered.
4. DONE: Replace demo condition logic with bounded simple condition evaluation and disabled expression conditions.
5. Implement real `voice_input`, `llm`, and `memory_save` chain:
   - `voice_input`: use supplied text in test mode or real VoiceEngine for live mode.
   - `llm`: call model router/Ollama and fail honestly when unavailable.
   - `memory_save`: store actual upstream output.

Acceptance tests:

- `voice_input -> llm -> memory_save` fails if LLM unavailable and passes only when response is stored.
- Workflow trace includes node output/error.
- UI shows real node status.
- Added regression coverage: `test_workflow_truthfulness.py` verifies unsupported capability nodes fail, executor-backed nodes pass, and notifications publish real events.

## Phase 4: Correct Asset And Data Paths

Priority: High

1. Move or copy `models/yolov8n.pt` into the path used by vision, or update model discovery to search configured model paths.
2. Decide whether active runtime data lives at root or under `nexora_os/`; prefer one.
3. Mark root logs/DBs as obsolete and remove after cleanup verification.
4. Add `.gitignore` entries for runtime logs, DBs, screenshots, generated sandboxes, and caches if missing.

Acceptance tests:

- Object detection attempts load from a real configured model path.
- No production code writes to duplicate root and package runtime folders unpredictably.

## Phase 5: Connect Existing UI Truthfully

Priority: High

1. DONE: Replace hardcoded VisionPage URLs with `nexoraApi` methods and add a source-contract regression test.
2. Remove UI controls that call placeholder backend flows or display unavailable state.
3. Add real degraded/unavailable indicators for:
   - Central Brain missing
   - STT timeout
   - LLM CLI degraded
   - object detection model disconnected
   - AI Lab disabled
4. Add Observability page only after backend metrics are reliable, or route metrics into existing panels with truthful labels.

Acceptance tests:

- Every nav page loads real backend data.
- DONE: No page depends on hardcoded localhost except central API config, covered by `test_frontend_api_contract.py`.
- No fake activity/random status values.

## Phase 6: Build Minimal Central Brain On Existing Systems

Priority: High, after Phases 1-5

Create `nexora_os/backend/brain/` by adapting existing modules rather than duplicating them:

- `brain_state.py`
- `goal_manager.py`
- `context_manager.py`
- `capability_registry.py`
- `model_router.py`
- `tool_router.py`
- `planner.py`
- `execution_engine.py`
- `observation_engine.py`
- `verifier.py`
- `reflection_engine.py`
- `cognitive_core.py`
- `autonomy_controller.py`

Implementation approach:

1. Register existing agents/workflows/tools/models as capabilities.
2. Route `/process` through `CognitiveCore.process_request()`.
3. Preserve simple direct commands where useful, but report cognitive stage and goal state.
4. Use bounded execution only.
5. Verify side effects before success.
6. Store meaningful experience to memory.

Acceptance tests:

- A typed command creates a goal.
- A plan is structured.
- Capabilities are selected dynamically.
- Execution result is observed and verified.
- UI Brain page shows real cognitive stage/current goal/current step.

## Phase 7: Voice, Vision, Automation End-To-End

Priority: Medium-High

Voice:

- Confirm microphone capture with user speech.
- Add clear STT timeout/error in UI.
- Route successful transcript through CognitiveCore.
- Speak final response through TTS.

Vision:

- Verify face detection with a known face frame or mark no-face test separately.
- Fix YOLO model path and object detection.
- Keep OCR and screen capture connected.

Automation:

- Add permission/risk checks before file delete, process kill, shutdown/restart, arbitrary shell/write operations.
- Verify app/browser/file side effects.

## Phase 8: Cleanup

Priority: After integration tests pass

Delete only after references, imports, config, dynamic loading, and tests are checked:

- old root logs/databases if not active
- generated agent sandboxes
- empty/dead folders
- obsolete rebrand script
- stale root reports replaced by `docs/` reports
- caches and generated artifacts

Document every deletion in `docs/CLEANUP_REPORT.md`.

## Phase 9: Final Validation

Generate after implementation and tests:

- `docs/TEST_REPORT.md`
- `docs/CLEANUP_REPORT.md`
- `docs/FINAL_SYSTEM_STATUS.md`

Do not claim completion until:

- app starts without critical crashes
- event delivery works
- central brain processes real request
- goals/plans/capabilities/model routing exist
- agents and workflows execute real tasks
- memory is used in response
- voice/camera status is honest
- UI shows real backend state
- tests pass or external blockers are documented
