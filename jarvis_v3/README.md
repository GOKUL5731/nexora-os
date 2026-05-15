# JARVIS vNext — GPU Edition
> Next-generation local-first AI assistant for Windows | RTX 4050 | Ollama | PySide6

---

## Quick Start (3 steps)

```powershell
# 1. Install base dependencies
pip install -r requirements.txt

# 2. Install GPU stack (PyTorch CUDA + faster-whisper + vision)
python setup_gpu.py

# 3. Launch
python -X utf8 jarvis_gui.py
```

Core OS health check:

```powershell
python -X utf8 main.py --core-health
python -X utf8 tests/test_core_os.py
```

`setup_gpu.py` now tries the current official Windows PyTorch CUDA wheels in order:
`cu128`, `cu126`, then `cu118`. Supported Python range for GPU setup is `3.10-3.14`.

**Hotkey:** `Ctrl+Space` → opens full dashboard

---

## Architecture

```
jarvis_v3/
├── jarvis_gui.py          ← Main launcher (GPU edition)
├── main.py                ← Terminal/voice fallback
├── setup_gpu.py           ← One-shot GPU installer
├── install.bat            ← Windows venv installer
├── start_jarvis.bat       ← Quick launch script
├── requirements.txt
│
├── core/
│   ├── config.py          ← Config loader + UTF-8 logging
│   ├── llm_client.py      ← LLM abstraction (Ollama/Claude/OpenAI)
│   ├── llm_router.py      ← Smart model selector (phi/mistral/llama3/deepseek)
│   ├── orchestrator.py    ← Central brain + task planner
│   ├── personality.py     ← Human-like JARVIS character engine
│   ├── voice.py           ← GPU STT (faster-whisper) + TTS (Piper/edge-tts)
│   ├── vision.py          ← GPU vision (easyocr/YOLOv8/face detection)
│   ├── coder.py           ← DeepSeek Coder copilot
│   ├── trainer.py         ← Behavior learning + response cache
│   ├── safety.py          ← Risk engine + audit trail
│   ├── benchmark.py       ← Latency/performance tracking
│   ├── plugin_manager.py  ← Hot-load plugins from plugins/
│   └── updater.py         ← Safe self-update pipeline
│
├── agents/
│   ├── agent_registry.py  ← Lazy-load all agents + plugin proxy
│   ├── web_agent.py       ← DuckDuckGo search + scraping
│   ├── system_agent.py    ← File ops + app control + clipboard
│   ├── voice_agent.py     ← Voice pipeline wrapper
│   ├── vision_agent.py    ← Screen/camera tools
│   ├── code_agent.py      ← Code execution + generation
│   ├── browser_agent.py   ← Playwright browser automation
│   └── memory_agent.py    ← SQLite memory tools
│
├── ui/
│   ├── widget.py          ← Floating glassmorphism HUD
│   └── dashboard.py       ← Full 7-tab command center
│
├── memory/
│   └── memory_manager.py  ← SQLite long-term + session memory
│
├── self_learning/
│   └── learning_engine.py ← Background self-improvement loop
│
├── plugins/
│   └── timers_plugin.py   ← Example: timers + reminders
│
├── android/
│   └── android_agent.py   ← ADB device control
│
├── database/              ← SQLite files (auto-created)
├── logs/                  ← jarvis.log (auto-created)
├── backups/               ← Updater backups (auto-created)
├── screenshots/           ← Vision captures (auto-created)
└── tests/
    └── test_all.py        ← 20-test suite (all pass)
```

---

## AI Model Stack

| Task | Model | Why |
|------|-------|-----|
| Instant commands | `phi` | Fastest, <200ms |
| General knowledge | `mistral` | Balanced speed/quality |
| Complex reasoning | `llama3` / `llama3.2` | Best local reasoning |
| Code writing | `deepseek-coder` | Purpose-built for code |
| Fallback | `gemma3` | Additional option |

Auto-routing: JARVIS picks the best model per query automatically.

**Install models:**
```powershell
ollama pull llama3.2
ollama pull deepseek-coder
ollama pull mistral
ollama pull phi
```

---

## Features by Phase

### Phase 1 — Foundation + UI ✅
- PySide6 glassmorphism floating widget
- Full 7-tab dashboard (Chat, System, Memory, Plugins, Benchmark, Logs, Updater)
- Ollama integration with model routing
- UTF-8 safe Windows logging

### Phase 2 — Voice ✅
- **STT:** faster-whisper on CUDA (RTX 4050 GPU) — multilingual EN+Tamil
- **TTS:** Piper TTS (offline) → edge-tts → pyttsx3 fallback chain
- Wake word: "Jarvis" — continuous background listening
- Interrupt speaking: stop mid-sentence instantly

### Phase 3 — Memory + PC Control ✅
- SQLite long-term memory (interactions, facts, skills, profile)
- Session context (mood, preferences, current project)
- Full file system control (read/write/delete/search)
- App control (open/close any app by name)
- Clipboard, volume, brightness, screenshots

### Phase 4 — Vision + Coding ✅
- GPU OCR with easyocr (English + Tamil)
- YOLOv8 object detection via webcam/screenshot
- Face detection (face_recognition / OpenCV fallback)
- Window listing (visible apps on screen)
- DeepSeek Coder copilot: write/debug/refactor/explain/test
- Auto-generate JARVIS plugins with syntax validation

### Phase 5 — Self-Learning ✅
- BehaviorTrainer: learns command frequency, favorite apps
- Response caching for repeated queries (reduces latency)
- LLM-generated behavioral insights every 30 min
- Personality engine: greetings, tone adaptation, proactive hints

### Phase 6 — Self-Upgrade ✅
- Safe patch pipeline: Backup → Syntax test → Import test → Deploy
- Protected core files cannot be overwritten
- Full update history in dashboard Updater tab
- One-click rollback to any previous version
- DeepSeek Coder can generate plugins autonomously

---

## GPU Performance (RTX 4050)

| Component | Backend | Acceleration |
|-----------|---------|-------------|
| Speech Recognition | faster-whisper | CUDA float16 |
| OCR | easyocr | CUDA |
| Object Detection | YOLOv8 | CUDA |
| LLM Inference | Ollama | llama.cpp GPU layers |
| GPU Monitoring | nvidia-ml-py | Native NVIDIA |

**Expected latency on RTX 4050:**
- Wake word → response: ~1.5-2.5s
- Code generation (100 lines): ~4-8s
- OCR full screen: ~0.8s
- Object detection: ~0.1s/frame

---

## Voice Commands (Examples)

```
"Jarvis, open VS Code"
"Jarvis, search for Python async tutorial"
"Jarvis, write a Python web scraper"
"Jarvis, take a screenshot"
"Jarvis, what's on my screen?"
"Jarvis, remember that I prefer dark mode"
"Jarvis, set a timer for 10 minutes"
"Jarvis, debug this error: [paste error]"
"Jarvis, organize my Downloads folder"
"Jarvis, what do you know about me?"
```

---

## Writing Plugins

Drop any `.py` file with a `register()` function into `plugins/`:

```python
def register(config: dict) -> dict:
    def my_tool(args: dict) -> dict:
        return {"result": "Hello from plugin!"}

    return {
        "name": "My Plugin",
        "version": "1.0.0",
        "description": "Does something useful.",
        "author": "your-name",
        "tools": {"my_tool": my_tool},
    }
```

JARVIS hot-loads it on next startup. Or ask JARVIS to write one:
> "Jarvis, create a plugin that monitors my CPU every minute"

---

## Running Tests

```powershell
python -X utf8 tests/test_all.py
# Expected: 20/20 PASS
```

---

## Configuration (`config/config.json`)

```json
{
  "llm": {
    "provider": "ollama",
    "model": "llama3.2",
    "coder_model": "deepseek-coder",
    "fallback_model": "mistral"
  },
  "voice": {
    "stt_device": "cuda",
    "stt_compute": "float16",
    "tts_backend": "edge_tts",
    "wake_word": "jarvis"
  },
  "vision": {
    "gpu": true
  }
}
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Ollama offline` | Run `ollama serve` in a terminal |
| `CUDA unavailable` | Run `setup_gpu.py` again; it now tries current PyTorch CUDA wheels and falls back to CPU mode only when verification fails |
| `PyAudio missing` | `pip install pipwin && pipwin install pyaudio` |
| `No Piper voice` | Download voice model to `models/piper/` |
| Unicode errors in console | Always use `python -X utf8 jarvis_gui.py` |
| Widget not on top | Right-click taskbar → check "Always on top" |

---

*Built with Python 3.14 · PySide6 · Ollama · faster-whisper · DeepSeek Coder*
