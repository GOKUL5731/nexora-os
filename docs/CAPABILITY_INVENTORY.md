# Capability Inventory

Audit date: 2026-07-10

## Runtime Capabilities

| Capability | Provider | Status | Evidence |
| --- | --- | --- | --- |
| API status | FastAPI | WORKING | `/status` returned 200 |
| API health | FastAPI + HealthMonitor | PARTIALLY WORKING | `/health` returns metrics; still needs explicit degraded policy for event-bus drops/errors |
| WebSocket state/events | FastAPI `/ws/events` + EventBus | PARTIALLY WORKING | Endpoint exists; async EventBus delivery is regression-tested, live browser WebSocket acceptance remains separate |
| Module registry | ModuleManager | PARTIALLY WORKING | 15 modules registered; no lifecycle contract |
| Startup/shutdown | NexoraRuntime | WORKING | startup ok, shutdown stopped async runtime |
| Logging | logger.py | WORKING | log files written under `nexora_os/logs` |
| CPU/RAM metrics | psutil | WORKING | API reported CPU/RAM/process memory |
| GPU metrics | pynvml | WORKING on this machine | API reported NVIDIA RTX 4050 GPU |

## AI Model Capabilities

| Capability | Provider | Status | Evidence |
| --- | --- | --- | --- |
| Local model discovery | Ollama HTTP `/api/tags` | WORKING | Models returned: `llama3.2:1b`, `phi`, `deepseek-coder`, plus more truncated in probe output |
| CLI model discovery | `ollama list` | DEGRADED | Command timed out after ~34 seconds |
| General text generation | OllamaClient | NOT VERIFIED | Model discovery works, but generation was not completed in this audit |
| Model routing by task | Missing | MISSING | No model router exists |
| Embedding model routing | Missing | MISSING | Memory uses deterministic hashing, not model embeddings |
| Vision-language routing | Missing | MISSING | No VLM integration found |

## Voice Capabilities

| Capability | Provider | Status | Evidence |
| --- | --- | --- | --- |
| Language detection | VoiceEngine regex/word list | WORKING | English, Tamil Unicode, and Tanglish tests passed |
| TTS | pyttsx3 | WORKING | `Jarvis voice test` returned `ok: true` |
| Microphone dependency | SpeechRecognition | AVAILABLE | Import and health checks pass |
| Live STT | SpeechRecognition Google recognizer | FAILED/TIMEOUT | No speech captured during 3 second listen window |
| Mic -> STT -> NLP -> LLM -> TTS | Combined pipeline | NOT VERIFIED | No end-to-end successful live voice command |

## Vision Capabilities

| Capability | Provider | Status | Evidence |
| --- | --- | --- | --- |
| Webcam open | OpenCV | WORKING | `VideoCapture(0)` opened |
| Frame capture | OpenCV | WORKING | `audit_camera_test.jpg` saved |
| Screen capture | PIL ImageGrab | WORKING | screenshot saved |
| OCR | pytesseract + Tesseract | WORKING | 1035 OCR characters returned |
| Face detection | OpenCV Haar cascade | NOT VERIFIED | Code exists; no positive face test was performed |
| Object detection | YOLO/ultralytics | DISCONNECTED | Model exists at root `models/yolov8n.pt`, code expects `nexora_os/models/yolov8n.pt` |
| Gesture/mouse control | OpenCV/pyautogui | PLACEHOLDER/PARTIAL | Motion heuristics exist; not verified and no permission policy |

## Memory Capabilities

| Capability | Provider | Status | Evidence |
| --- | --- | --- | --- |
| Chunk storage | MemoryEngine SQLite | WORKING | marker stored, 1 chunk |
| Embeddings | Hash vector | PARTIALLY WORKING | deterministic vector search works, not semantic model embeddings |
| Retrieval | MemoryEngine search | WORKING | marker retrieved as top result |
| Reflection | MemoryEngine reflect | PLACEHOLDER/PARTIAL | summarizes categories only |
| Retention policy | Missing | MISSING | No cleanup/importance retention policy |
| Relationship graph | MemoryEngine network | PARTIALLY WORKING | sequential edges from latest memories, not semantic relationships |

## Agent Capabilities

| Agent | Runtime key | Status | Evidence |
| --- | --- | --- | --- |
| PlannerAgent | `PlannerAgent` | WORKING/PARTIAL | real exported planner class; produces bounded plan with static fallback and is active in `/agents` |
| AutonomousAgent | inactive source class | DISABLED/RISKY | source remains, but it is not registered until shell/file/browser tool execution has central permission and verification |
| VoiceAgent | `VoiceAgent` | PARTIALLY WORKING | delegates status/listen/speak to VoiceEngine |
| VisionAgent | `VisionAgent` | PARTIALLY WORKING | delegates status/start/capture/screen to VisionEngine |
| WorkflowAgent | `WorkflowAgent` | PARTIALLY WORKING | delegates workflow run; missing workflow returns error |
| ResearchAgent | none | MISSING/DISABLED | submit returns unknown agent |
| CodingAgent | none | MISSING/DISABLED | submit returns unknown agent |

## Workflow Capabilities

| Capability | Status | Notes |
| --- | --- | --- |
| Save workflow | WORKING | SQLite persistence works |
| List workflow | WORKING | API returns existing workflows |
| Trace workflow | WORKING | Trace rows written |
| Execute graph order | PARTIALLY WORKING | DAG traversal works |
| Retry failed nodes | PARTIALLY WORKING | Exception retry exists |
| Verify node output | PARTIALLY WORKING | Executor `ok: false` fails the node and outputs are returned in workflow results; per-capability side-effect verification is still incomplete |
| `memory_save` node | WORKING VIA RUNTIME | Stores text to memory when the runtime executor is wired; standalone WorkflowEngine now fails honestly without an executor |
| `camera`/`ocr` nodes | PARTIALLY WORKING | Routed to screen capture, not webcam camera node |
| `voice_input` node | PLACEHOLDER | Completes without voice input |
| `llm` node | PLACEHOLDER | Completes without LLM call |
| `browser` node | PLACEHOLDER | Completes without browser action |
| `notify` node | PLACEHOLDER | Completes without notification |
| `condition` node | PLACEHOLDER | Returns true for demonstration |
| Scheduler | PARTIALLY WORKING | Loop exists, not stress tested |

## Automation Capabilities

| Capability | Status | Notes |
| --- | --- | --- |
| System status | WORKING | Returned `Windows 10 on AMD64` |
| Time | LIKELY WORKING | Code path exists, not separately verified |
| Screenshot | WORKING | Through vision screen capture |
| OCR screen | WORKING | Through vision OCR |
| Launch app | PARTIALLY WORKING | Starts process/app but does not verify state |
| Browser open | PARTIALLY WORKING | Uses `webbrowser.open`, no DOM automation |
| File create/read/delete | PARTIALLY WORKING/RISKY | Uses current working directory, lacks permission policy |

## UI Page Capability Map

| Page/Nav | Status | Backend data |
| --- | --- | --- |
| Home | PARTIALLY WORKING | Shared status/modules/events/memory |
| Brain | PLACEHOLDER/PARTIAL | Shows activity/agent steps, but no real central brain state |
| Voice | PARTIALLY WORKING | `/voice/status`, `/voice/listen`, `/voice/speak` |
| Vision | PARTIALLY WORKING | `/vision/status`, `/vision/frame`, `/vision/screen`; frontend now routes through central API client, but live hardware/object-detection acceptance remains separate |
| Agents | PARTIALLY WORKING | `/agents`, `/agents/{name}/tasks`; four-agent recovery contract is tested, richer central-brain supervision remains incomplete |
| Workflows | PARTIALLY WORKING | graph CRUD/run/trace |
| Automation | PARTIALLY WORKING | `/automation`, `/automation/run` |
| Memory | WORKING/PARTIAL | `/memory`, `/memory/network`, `/memory/reflect` |
| AI Lab | DISCONNECTED/PARTIAL | Settings/LLM diagnostics only; generator backend still exposed |
| Settings | PARTIALLY WORKING | `/settings` |
| Observability | MISSING AS PAGE | Metrics appear in shared panels, no dedicated page |
