# MODULE DEPENDENCY MAP

Generated: 2026-06-27
Mode: NEXORA Recovery & Stabilization

## Dependency Graph

```
nexora_os/backend/
├── core/
│   ├── event_bus.py (NO DEPENDENCIES - CORE)
│   ├── logger.py (NO DEPENDENCIES - CORE)
│   ├── module_manager.py → event_bus.py
│   ├── async_runtime.py → event_bus.py
│   ├── health_monitor.py → event_bus.py, module_manager.py, agents/runtime.py, workflows/engine.py, memory/engine.py, async_runtime.py
│   ├── llm.py (NO EXTERNAL DEPENDENCIES - uses requests)
│   └── runtime.py → agents/runtime.py, ai_lab/agent_creator.py, automation/engine.py, memory/engine.py, vision/engine.py, voice/engine.py, workflows/engine.py, event_bus.py, async_runtime.py, health_monitor.py, llm.py, logger.py, module_manager.py
│
├── agents/
│   └── runtime.py → core/event_bus.py, memory/engine.py
│
├── ai_lab/
│   └── agent_creator.py → core/event_bus.py
│
├── automation/
│   └── engine.py → core/event_bus.py, vision/engine.py
│
├── memory/
│   └── engine.py → core/event_bus.py
│
├── monitoring/
│   └── system_monitor.py → (uses psutil, pynvml - no internal deps)
│
├── vision/
│   └── engine.py → core/event_bus.py
│
├── voice/
│   └── engine.py → core/event_bus.py
│
├── workflows/
│   └── engine.py → core/event_bus.py
│
└── api/
    └── app.py → core/runtime.py (via runtime instance)
```

## Module Level Hierarchy

### Level 0: Core Foundation (No Internal Dependencies)
- `core/event_bus.py` - Event system
- `core/logger.py` - Logging system
- `core/llm.py` - LLM client

### Level 1: Core Infrastructure (Depends on Level 0)
- `core/module_manager.py` → event_bus.py
- `core/async_runtime.py` → event_bus.py
- `memory/engine.py` → event_bus.py
- `voice/engine.py` → event_bus.py
- `vision/engine.py` → event_bus.py
- `workflows/engine.py` → event_bus.py
- `agents/runtime.py` → event_bus.py, memory/engine.py
- `ai_lab/agent_creator.py` → event_bus.py

### Level 2: Cross-Module Integration (Depends on Level 0-1)
- `automation/engine.py` → event_bus.py, vision/engine.py
- `monitoring/system_monitor.py` → (no internal deps, external only)

### Level 3: System Orchestration (Depends on Level 0-2)
- `core/health_monitor.py` → event_bus.py, module_manager.py, agents/runtime.py, workflows/engine.py, memory/engine.py, async_runtime.py
- `core/runtime.py` → agents/runtime.py, ai_lab/agent_creator.py, automation/engine.py, memory/engine.py, vision/engine.py, voice/engine.py, workflows/engine.py, event_bus.py, async_runtime.py, health_monitor.py, llm.py, logger.py, module_manager.py

### Level 4: API Layer (Depends on Level 3)
- `api/app.py` → core/runtime.py

## Initialization Order

1. **Event Bus** (`core/event_bus.py`) - Must be first
2. **Logger** (`core/logger.py`) - Can be parallel with event bus
3. **Module Manager** (`core/module_manager.py`) - Depends on event bus
4. **Async Runtime** (`core/async_runtime.py`) - Depends on event bus
5. **Memory Engine** (`memory/engine.py`) - Depends on event bus
6. **Voice Engine** (`voice/engine.py`) - Depends on event bus
7. **Vision Engine** (`vision/engine.py`) - Depends on event bus
8. **Workflow Engine** (`workflows/engine.py`) - Depends on event bus
9. **Agent Runtime** (`agents/runtime.py`) - Depends on event bus, memory
10. **AI Lab Creator** (`ai_lab/agent_creator.py`) - Depends on event bus
11. **Automation Engine** (`automation/engine.py`) - Depends on event bus, vision
12. **LLM Client** (`core/llm.py`) - No internal deps
13. **Health Monitor** (`core/health_monitor.py`) - Depends on most modules
14. **Main Runtime** (`core/runtime.py`) - Orchestrates all above
15. **API** (`api/app.py`) - Depends on runtime

## Shutdown Order (Reverse of Initialization)

1. **API** (`api/app.py`) - First to stop
2. **Main Runtime** (`core/runtime.py`) - Orchestrates shutdown
3. **Health Monitor** (`core/health_monitor.py`) - Before runtime stops
4. **Agent Runtime** (`agents/runtime.py`) - Stop agents
5. **Workflow Engine** (`workflows/engine.py`) - Stop workflows
6. **Async Runtime** (`core/async_runtime.py`) - Stop async tasks
7. **Automation Engine** (`automation/engine.py`) - Cleanup
8. **Vision Engine** (`vision/engine.py`) - Release camera
9. **Voice Engine** (`voice/engine.py`) - Release audio
10. **Memory Engine** (`memory/engine.py`) - Close database
11. **AI Lab Creator** (`ai_lab/agent_creator.py`) - Cleanup
12. **Module Manager** (`core/module_manager.py`) - Last internal
13. **Event Bus** (`core/event_bus.py`) - Last to stop
14. **Logger** (`core/logger.py`) - Final cleanup

## External Dependencies

### Python Packages
- `fastapi` - API framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation
- `psutil` - System monitoring
- `Pillow` - Image processing
- `opencv-python` - Computer vision
- `SpeechRecognition` - Speech-to-text
- `pyttsx3` - Text-to-speech
- `pytesseract` - OCR
- `pyautogui` - Mouse/keyboard control

### External Services
- **Ollama** - LLM service (127.0.0.1:11434)
- **Tesseract OCR** - OCR executable (C:\Program Files\Tesseract-OCR\tesseract.exe)
- **YOLO Model** - Object detection model (models/yolov8n.pt)

### Hardware Dependencies
- **Microphone** - Audio input (requires Windows configuration)
- **Camera** - Video input (webcam)
- **GPU** - Optional for acceleration (NVIDIA CUDA)

## Circular Dependency Analysis

**No circular dependencies detected.**

The dependency graph is acyclic with clear initialization order.

## Module Coupling Analysis

### Low Coupling (Good)
- `core/event_bus.py` - No internal dependencies
- `core/logger.py` - No internal dependencies
- `core/llm.py` - No internal dependencies
- `monitoring/system_monitor.py` - No internal dependencies

### Medium Coupling (Acceptable)
- `memory/engine.py` - Only depends on event_bus
- `voice/engine.py` - Only depends on event_bus
- `vision/engine.py` - Only depends on event_bus
- `workflows/engine.py` - Only depends on event_bus
- `agents/runtime.py` - Depends on event_bus and memory

### High Coupling (Concerning)
- `core/runtime.py` - Depends on almost everything (expected for orchestrator)
- `core/health_monitor.py` - Depends on many modules (expected for monitoring)
- `automation/engine.py` - Depends on vision (specific coupling)

## Critical Path Analysis

**Critical Path for Basic Operation:**
```
event_bus → logger → module_manager → async_runtime → memory → agents → runtime → API
```

**Critical Path for Voice:**
```
event_bus → voice → runtime → API
```

**Critical Path for Vision:**
```
event_bus → vision → automation → runtime → API
```

**Critical Path for Workflows:**
```
event_bus → memory → workflows → runtime → API
```

## Module Health Impact

### Critical Failure Impact
- **event_bus.py** - Complete system failure
- **runtime.py** - Complete system failure
- **async_runtime.py** - Async operations fail
- **memory/engine.py** - Memory operations fail, agents lose context

### High Failure Impact
- **agents/runtime.py** - Agent tasks fail
- **workflows/engine.py** - Workflow execution fails
- **vision/engine.py** - Vision features fail, automation affected
- **voice/engine.py** - Voice features fail

### Medium Failure Impact
- **automation/engine.py** - Automation features fail
- **health_monitor.py** - Monitoring fails (system still works)
- **module_manager.py** - Module status unknown (system still works)

### Low Failure Impact
- **llm.py** - LLM features fail (system still works)
- **ai_lab/agent_creator.py** - AI Lab features fail (system still works)
- **monitoring/system_monitor.py** - System monitoring fails (system still works)

## Recommendations

1. **Reduce coupling**: Consider breaking automation's dependency on vision
2. **Improve modularity**: Extract common patterns from engines
3. **Dependency injection**: Use dependency injection for better testability
4. **Interface segregation**: Define clear interfaces between modules
5. **Event-driven**: Increase use of event_bus for loose coupling
