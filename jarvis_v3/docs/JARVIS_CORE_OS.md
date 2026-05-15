# JARVIS CORE OS Operator Manual

This project is local-first. Ollama, faster-whisper, Piper, SQLite, OpenCV, OCR,
and PySide6 run on the Windows machine. Cloud LLM providers are disabled unless
explicitly enabled in code/config.

## Install

```powershell
cd jarvis_v3
pip install -r requirements.txt
python setup_gpu.py
ollama pull llama3.2
ollama pull deepseek-coder
ollama pull mistral
ollama pull phi
```

For Piper, place voice models under `models/piper/<voice-name>/`.

## Run

```powershell
python -X utf8 main.py
python -X utf8 main.py --voice
python -X utf8 jarvis_gui.py
python -X utf8 main.py --core-health
```

## Automated Tests

```powershell
python -X utf8 tests/test_all.py
python -X utf8 tests/test_core_os.py
```

Expected output: all tests pass. If Ollama is offline, live model tests are skipped
or return an explicit offline message.

## Module Matrix

| Module | Purpose | Manual test | Expected output | Failure handling |
|---|---|---|---|---|
| `core/llm_router.py` | Routes prompts to phi, mistral, llama3.2, or deepseek-coder. | `python -X utf8 main.py --core-health` | `ollama_running` plus local model list. | Falls back to available model or returns Ollama offline guidance. |
| `core/command_engine.py` | Direct no-LLM execution for safe frequent commands. | In chat: `what time is it`, `status`, `remember that I prefer dark mode`. | Immediate response with confidence. | Unknown commands fall through to planner; high-risk terminal commands request confirmation. |
| `memory/memory_manager.py` / `core/memory_engine.py` | Long-term, episodic, preference, error, and vector memory in SQLite. | Run `tests/test_core_os.py`. | Stored events/preferences/vector matches are returned. | Missing vector deps do not matter; local hashed vectors are used. |
| `core/voice_engine.py` / `core/tts_engine.py` | faster-whisper STT and Piper/pyttsx3 TTS. | `python -X utf8 main.py --voice`. | Wake word listener starts. | CUDA falls back to CPU; missing Piper falls back to configured TTS chain. |
| `core/vision_engine.py` | Screen OCR, object detection, webcam capture. | Ask: `take screenshot`; call OCR from dashboard/agent. | Screenshot path or OCR text. | Missing OCR/CV packages return install guidance instead of crashing. |
| `agents/system_agent.py` | File, clipboard, app, screenshot, and terminal actions. | In chat: `status`; `take screenshot`. | System metrics or saved screenshot. | Destructive tools are high-risk in planner and require confirmation. |
| `core/sandbox_engine.py` | Process-level sandbox for generated code. | `python -X utf8 tests/test_core_os.py`. | Sandbox command returns `ok: true`. | Timeouts, stderr, cwd, and command are logged to `logs/sandbox_audit.jsonl`. |
| `core/upgrade_engine.py` | Self-analysis, plugin generation, sandbox validation, deployment, rollback metadata. | `python -X utf8 tests/test_core_os.py`; dashboard Updater tab for history. | Codebase analysis and plugin sandbox pass. | Protected boot files are refused; failed candidates stay in sandbox and are not deployed. |
| `core/reliability_engine.py` | Confidence scoring, bounded retry, fallback responses. | `python -X utf8 tests/test_core_os.py`. | Retry succeeds within bounded attempts. | Failures are written to error memory when memory is available. |
| `core/benchmark_engine.py` | Latency and success metrics in SQLite. | Dashboard Benchmark tab. | Recent operation timings. | Empty reports return `count: 0` cleanly. |
| `core/learning_engine.py` | Combined behavior trainer and self-learning lifecycle. | Start GUI or chat mode and inspect learned summary. | Command frequencies, app usage, and strategy summary. | LLM insight generation is skipped when Ollama is offline. |
| `core/jarvis_core_os.py` | Unified OS-layer facade for CLI/UI/service usage. | `python -X utf8 main.py --core-health`. | JSON health report. | Optional GPU/model fields show clear reasons when unavailable. |

## Safe Self-Upgrade Rules

The evolution engine follows this contract:

1. Analyze codebase and record benchmark timing.
2. Generate candidate plugin/module code with local DeepSeek Coder through Ollama.
3. Run static safety checks.
4. Write candidate into `sandbox/`.
5. Compile and import in a separate process.
6. Validate plugin `register()` contract or module importability.
7. Deploy only if tests pass.
8. Create backups for existing plugin/module targets.
9. Log deployment and rollback metadata.
10. Refuse protected boot files.

Protected files include `main.py`, `jarvis_gui.py`, `core/config.py`,
`core/updater.py`, `core/upgrade_engine.py`, `core/safety.py`,
`core/permission_engine.py`, and `agents/agent_registry.py`.

## Background Mode

Use Windows Task Scheduler or a Startup shortcut pointing to:

```powershell
python -X utf8 jarvis_gui.py
```

The GUI keeps the floating widget available and the dashboard accessible through
`Ctrl+Space` when the `keyboard` package has permission to register the hotkey.
