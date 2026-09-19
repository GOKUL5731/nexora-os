# G Acceptance Report

Date: 2026-09-19

## Architecture

The active implementation is a Python/FastAPI backend with a React/TypeScript/Vite Command Center and a PySide6 desktop wrapper. Core runtime, event bus, cognitive routing, memory, agents, workflows, connectors, orchestration, security, voice, vision, and MCP-related modules are present under `nexora_os`.

## Working features verified in this checkpoint

- Focused core runtime, event recovery, conversation routing, orchestration, and monitor-truthfulness tests: 10 passed.
- Python backend compilation succeeds.
- Frontend production build succeeds.
- Windows launcher performs location-relative preflight and explicit dependency checks.

## Partially available

Live microphone, camera, OCR, local model, MCP/plugin, external coding-agent, multi-monitor, and interactive Windows UI Automation behavior require environment-specific verification. The launcher reports optional capability gaps instead of fabricating readiness.

## Remaining blockers

The full G acceptance scenarios—especially supervised Codex/Cursor/Antigravity work, conflict-safe integration, restart recovery, and live Windows control—do not yet have executable evidence in this environment.

## How to run

Double-click `run_project.cmd` for the Windows one-click path. Use `run_project.cmd --check` for preflight only. The frontend can be built from `nexora_os/frontend` with `npm run build`.
