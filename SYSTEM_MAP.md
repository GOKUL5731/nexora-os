# JARVIS SYSTEM MAP

Fix Mode audit date: 2026-05-15

## Purpose

This document maps the current JARVIS platform before further expansion. The priority is core runtime stabilization:

```text
Stability -> Reliability -> Observability -> Integration -> Expansion
```

No advanced AI features should be added until the core runtime is stable.

## Frontend

Folder:

- `jarvis_ui/`
- `jarvis_v3/ui/`
- `jarvis_v3/jarvis_visual_core/ui/`

Contains:

- dashboard
- orb
- workflow visualization
- animations
- system panels
- voice panels
- observability/debug views

Current problems:

- UI synchronization depends on polling shared state instead of a strict UI event bridge.
- Some visual components historically used decorative/random activity.
- Multiple UI entrypoints exist (`jarvis_gui.py`, `hud.py`, `main.py --gui`), which can initialize different backend subsets.
- Backend disconnects are possible when optional engines fail during startup.
- Update cadence is inconsistent across panels.

Fix-mode rule:

- UI must display only real backend state from `core.event_bus`, `core.health_monitor`, `core.module_manager`, and concrete subsystem APIs.
- No fake activity, placeholder agents, or cinematic expansion work belongs in this phase.

## Backend

Folder:

- `jarvis_v3/`

Contains:

- voice
- memory
- agents
- workflows
- automation
- plugins
- AI systems
- CNN/RNN systems
- AI LAB components

Current problems:

- Event communication is present but not yet enforced everywhere.
- Module lifecycle tracking exists but many modules do not expose a formal `start/stop/restart/health_check/status` contract.
- Async work is scattered across ad hoc event loops, Qt threads, background threads, and direct calls.
- Some workflows execute shell/file actions directly and need stronger runtime supervision.
- Agent failures are logged, but recovery and dependency awareness need hardening.
- Observability exists but is split between logs, SQLite traces, event history, and dashboard polling.
- State management is inconsistent between CLI, GUI, visual runtime, and legacy dashboard launchers.

## Core Runtime Infrastructure

Mandatory core files:

```text
jarvis_v3/core/
├── event_bus.py
├── module_manager.py
├── logger.py
├── health_monitor.py
└── async_runtime.py
```

### Event Bus

File: `jarvis_v3/core/event_bus.py`

Role:

- Nervous system for runtime events and shared state.
- Supports sync and async subscribers.
- Tracks event history, subscriber counts, published count, and subscriber errors.

Required module behavior:

- Publish lifecycle, status, error, health, and execution events.
- Prefer events over direct UI mutation or cross-module coupling.

### Module Manager

File: `jarvis_v3/core/module_manager.py`

Role:

- Tracks module lifecycle and dependencies.
- Supports startup, shutdown, restart, failure tracking, and health checks.

Required module contract:

```python
start()
stop()
restart()
health_check()
status()
```

Supported statuses:

- `loading`
- `starting`
- `running`
- `online`
- `failed`
- `restarting`
- `disabled`

### Central Logger

File: `jarvis_v3/core/logger.py`

Role:

- Queue-backed async-safe logging.
- Rotating log files.
- Event-bus mirrored logs.
- Timing context for startup/shutdown/execution measurements.

Required logging points:

- startup
- shutdown
- warnings
- errors
- execution timing

### Health Monitor

File: `jarvis_v3/core/health_monitor.py`

Role:

- Generates live runtime snapshots and health reports.
- Publishes alerts when modules fail or runtime infrastructure reports errors.

Monitors:

- CPU
- GPU
- RAM
- active modules
- workflow queue
- agents
- thread health
- event bus health
- async runtime health

### Async Runtime

File: `jarvis_v3/core/async_runtime.py`

Role:

- Owns the background asyncio loop.
- Runs blocking work in a bounded thread pool.
- Gives UI code a safe way to submit background tasks.
- Tracks task state and publishes lifecycle events.

Separation targets:

- UI thread
- AI inference
- voice processing
- workflows
- automation
- deep learning tasks

## Fix Priority

1. Event Bus
2. Module Manager
3. Logging
4. Health Monitor
5. Async Runtime
6. Voice System
7. Memory
8. Automation
9. Agent Framework
10. CNN/RNN
11. UI synchronization

## Stabilization Tests

Required test classes:

- startup/shutdown
- event delivery
- module recovery
- async stability
- thread safety
- error handling
- logging accuracy
- health snapshot correctness

Current stabilization test file:

- `jarvis_v3/tests/test_runtime_infrastructure.py`

## Reconnection Policy

Reconnect subsystems only after core infrastructure is stable:

- voice
- memory
- automation
- agents
- workflows
- CNN/RNN
- UI

Every reconnection must:

- register with `ModuleManager`
- publish state through `EventBus`
- log through centralized logger
- provide health data
- avoid blocking the UI thread
