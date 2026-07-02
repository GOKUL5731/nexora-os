# PROJECT AUDIT

Audit date: 2026-06-16
Mode: NEXORA Recovery Mode

## Current Repository Shape

The repository currently contains one consolidated source root:

- `nexora_os/`

Top-level launch/build files:

- `NEXORA_ONE_CLICK.cmd`
- `BUILD_WINDOWS_EXE.cmd`

Required target folders exist:

- `nexora_os/frontend`
- `nexora_os/backend`
- `nexora_os/plugins`
- `nexora_os/models`
- `nexora_os/databases`
- `nexora_os/logs`
- `nexora_os/tests`
- `nexora_os/docs`

## Working Modules

- Backend API starts under `nexora_os.backend.api.app`
- Command Center UI source exists under `nexora_os/frontend`
- Event bus file exists: `nexora_os/backend/core/event_bus.py`
- Module manager file exists: `nexora_os/backend/core/module_manager.py`
- Memory engine stores chunks and deterministic vector embeddings in SQLite
- Workflow engine stores graphs and traces in SQLite
- Monitoring reports CPU/RAM/GPU/event traffic through `/health` and `/status`
- Windows desktop wrapper exists through `nexora_os/desktop_app.py`

Verified during audit:

- `GET /status`: 200
- `GET /health`: 200
- `GET /state`: 200
- `GET /events`: 200
- `GET /agents`: 200
- `GET /workflows`: 200
- `GET /memory`: 200
- `GET /memory/network`: 200
- `GET /voice/status`: 200
- `GET /vision/status`: 200
- `GET /automation`: 200
- `GET /settings`: 200

## Partially Working Modules

- Voice: TTS/STT adapters exist, but microphone and speaker have not been verified end-to-end in Recovery Mode.
- Vision: webcam/screen/OCR/object-detection adapter code exists, but webcam frame updates, face detection, object detection, and OCR have not been verified with live hardware in Recovery Mode.
- LLM: Ollama bridge exists, but audit found no installed local model through the API test path.
- Automation: status endpoint exists; application launch, file operations, and browser automation are not fully implemented/test-proven.
- Workflow: graph creation/storage/execution exists; required test workflow `Voice Input -> LLM -> Memory Save` is not yet verified end-to-end.
- UI: all official pages exist, but several pages still need verification for real backend data and removal of any inert/fallback-only UI behavior.

## Broken Modules / Recovery Gaps

- Core runtime files now exist (logger.py, health_monitor.py, async_runtime.py were added since 2026-06-12 audit).
- Runtime registers six agents instead of the required four. Current extra agents:
  - `ResearchAgent`
  - `CodingAgent`
- Generated AI Lab agent sandboxes exist under `nexora_os/ai_lab_sandbox`; Recovery Mode says stop creating agents and reduce agents.
- Frontend API client references routes that do not exist:
  - `GET /tools`: 404
  - `POST /nlp/process`: 404
  - `POST /lab/sandbox`: 404

## Disconnected Modules

- UI `nexoraApi.tools()` is disconnected from backend.
- UI `nexoraApi.nlpProcess()` is disconnected from backend.
- UI `nexoraApi.labSandbox()` is disconnected from backend.
- LLM does not participate in the default non-`ask` command path, so `Mic -> STT -> NLP -> LLM -> TTS` is not proven.
- Voice page can call listen/speak, but it does not show independent stage diagnostics for Mic, STT, NLP, LLM, TTS, Speaker.
- Vision page can start/stop/capture, but it does not yet display verified live frame update status.
- Automation page exposes registered actions only; browser automation and file-operation tools are missing or unproven.

## Duplicate Systems

Legacy source trees (`nexora_ui/`, `nexora_v3/`, root `database/`, root `sandbox/`) have already been removed from the filesystem.

Remaining duplicates/prototypes:

- None (ai_lab_sandbox, generated_agents.json, and duplicate docs removed in Phase 9)

## Dead / Obsolete Code

- `BUILD_WINDOWS_EXE.cmd` is packaging support, not runtime code.
- AI Lab generated agents and sandbox removed in Phase 9.
- AI Lab agent generation should be disabled until base system works.

## Audit Conclusion

The repository is mostly consolidated, but it is not yet a verified working Nexora system. Recovery work must focus on:

1. Restoring/adding the required core runtime files.
2. Reducing active agents to the required four.
3. Fixing disconnected UI/API routes.
4. Proving voice, camera, memory, workflow, automation, and observability end-to-end.
5. Removing generated agents and remaining dead artifacts.
