# BROKEN MODULES

Audit date: 2026-06-16

## Critical

### Missing Core Runtime Files

Recovery Mode requires these files:

- `event_bus.py`: present
- `module_manager.py`: present
- `logger.py`: present (added since 2026-06-12 audit)
- `health_monitor.py`: present in `backend/core` (added since 2026-06-12 audit)
- `async_runtime.py`: present (added since 2026-06-12 audit)

Impact:

- Core runtime files are now present and functional.

### Agent Runtime Does Not Match Recovery Scope

Required agents:

- PlannerAgent
- VoiceAgent
- WorkflowAgent
- VisionAgent

Current runtime includes:

- PlannerAgent
- VoiceAgent
- VisionAgent
- ResearchAgent
- WorkflowAgent
- CodingAgent

Impact:

- Experimental/non-required agents are active.
- Recovery Mode explicitly says reduce agents and disable experimental agents.

### Broken API Routes Referenced By Frontend Client

These frontend client methods point to missing backend routes:

- `GET /tools`: returns 404
- `POST /nlp/process`: returns 404
- `POST /lab/sandbox`: returns 404

Impact:

- Any UI component or future call using those methods will fail.

## High

### Voice End-To-End Not Verified

Current state:

- `/voice/status` returns 200.
- STT (SpeechRecognition) and TTS (pyttsx3) packages are installed and available.
- Language detection works for English, Tamil, and Tanglish.
- TTS tested and working: can speak text.
- STT code exists but microphone hardware not verified (timeout in test).
- LLM not ready: Ollama not running or no local model installed.
- No independent diagnostic result for each stage in UI.

Impact:

- Nexora can speak but cannot hear or process through LLM until Ollama is configured.

### Camera End-To-End Not Verified

Current state:

- `/vision/status` returns 200.
- Webcam start/stop/capture tested and working (640x480).
- Screen capture tested and working (1920x1200).
- Face detection code exists but returned empty in test (may need faces in image).
- Object detection requires YOLO model in models/ directory (not present).
- OCR (pytesseract) runs but returns empty text (tesseract executable may not be installed).

Impact:

- Basic webcam and screen capture work. Face/object detection and OCR need configuration.

### LLM Not Ready

Current state:

- Ollama bridge exists.
- API test reports no local model installed.

Impact:

- `Mic -> STT -> NLP -> LLM -> TTS -> Speaker` cannot complete through a real LLM until a model exists.

## Medium

### Automation Incomplete

Required checks:

- Application launch
- File operations
- Browser automation

Current state:

- Automation exposes safe actions: system status, time, screenshot, OCR (all tested and working).
- App launch: NOT implemented.
- File operations: NOT implemented.
- Browser automation: NOT implemented.

### Workflow Required Test Missing

Required workflow:

```text
Voice Input -> LLM -> Memory Save
```

Current state:

- Workflow engine can store and execute graphs.
- Required voice/LLM/memory workflow is not verified end-to-end.

### AI Lab Generated Agent Artifacts

Current state:

- Generated agent sandboxes remain in `nexora_os/ai_lab_sandbox`.
- Generated agent registry remains in `nexora_os/databases/generated_agents.json`.

Impact:

- Recovery Mode says stop creating new agents and reduce the system.

## Low

### Documentation Claims Need Tightening

`SYSTEM_STATUS.md` contains prior success claims that are too broad for Recovery Mode because voice/camera/hardware paths have not been fully tested.
