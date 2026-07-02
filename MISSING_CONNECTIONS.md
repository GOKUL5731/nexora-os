# MISSING CONNECTIONS

Audit date: 2026-06-16

## UI To Backend

| UI/API Client Method | Backend Route | Status |
|---|---:|---|
| `nexoraApi.tools()` | `GET /tools` | Missing, returns 404 |
| `nexoraApi.nlpProcess()` | `POST /nlp/process` | Missing, returns 404 |
| `nexoraApi.labSandbox()` | `POST /lab/sandbox` | Missing, returns 404 |
| `status()` | `GET /status` | Connected |
| `health()` | `GET /health` | Connected |
| `agents()` | `GET /agents` | Connected |
| `workflows()` | `GET /workflows` | Connected |
| `memory()` | `GET /memory` | Connected |
| `voiceListen()` | `POST /voice/listen` | Connected, hardware not proven |
| `voiceSpeak()` | `POST /voice/speak` | Connected, speaker not proven |
| `visionStart()` | `POST /vision/webcam/start` | Connected, camera not proven |
| `visionStop()` | `POST /vision/webcam/stop` | Connected |
| `visionCapture()` | `POST /vision/capture` | Connected, camera not proven |
| `visionScreen()` | `POST /vision/screen` | Connected |
| `automation()` | `GET /automation` | Connected |
| `automationRun()` | `POST /automation/run` | Connected |
| `settings()` | `GET /settings` | Connected |

## Required Pipeline Connections

### Voice Pipeline

Required:

```text
Microphone -> STT -> NLP -> LLM -> TTS -> Speaker
```

Current connection state:

- Microphone -> STT: code path exists, hardware not verified (timeout in test).
- STT -> NLP: language detection works, command handling goes through `process`.
- NLP -> LLM: LLM only used when command starts with `ask` or `llm`; Ollama not ready.
- LLM -> TTS: not wired as a guaranteed voice response path.
- TTS -> Speaker: TTS tested and working (pyttsx3).

### Camera Pipeline

Required:

```text
Webcam -> Frame Update -> Face Detection -> Object Detection -> OCR -> UI
```

Current connection state:

- Webcam start/stop/capture tested and working.
- Screen capture tested and working.
- Face detection code exists but needs faces in image to verify.
- Object detection requires YOLO model (not present in models/).
- OCR runs but needs tesseract executable configured.
- UI displays JSON status from capture/screen functions.

### Memory Pipeline

Required:

```text
Store memory -> Retrieve memory -> Use memory in response
```

Current connection state:

- Store: tested and working (chunk creation, embedding generation, SQLite storage).
- Retrieve: tested and working (vector similarity search, scoring).
- Use in response: agents receive memory context in execute() method.

### Workflow Pipeline

Required:

```text
Voice Input -> LLM -> Memory Save
```

Current connection state:

- Workflow nodes exist for `voice_input`, `llm`, and `memory_save`.
- Workflow creation, storage, execution, and logging tested and working.
- Test workflow (trigger -> memory_save) executed successfully with trace logging.
- Node executor implements memory_save; voice_input and llm need LLM configured.

### Agent Health Pipeline

Required agents:

- PlannerAgent
- VoiceAgent
- WorkflowAgent
- VisionAgent

Current connection state:

- Agents can report health through `/agents`.
- Runtime has extra active agents.
- Agent page can queue task calls, but health does not yet hide disabled/removed agents because they are not removed.

### Automation Pipeline

Required:

- Application launch
- File operations
- Browser automation

Current connection state:

- App launch: NOT implemented.
- File operations: NOT implemented.
- Browser automation: NOT implemented.
- Screenshot/OCR/system/time actions tested and working.

## Summary

The Command Center is the correct official UI, and the backend is reachable. Missing work is mostly integration hardening, not UI redesign.
