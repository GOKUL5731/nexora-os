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

## Live acceptance matrix

| Scenario | Implementation | Automated test | Live test | Result |
|---|---|---|---|---|
| Fast/task routing | Present | Passed focused routing suite | Not run in this checkpoint | VERIFIED automated path |
| Process/window discovery | `DesktopConnector` | Contract tests passed | Windows query returned 8 visible windows | PASS |
| Monitor discovery | `DesktopConnector.list_monitors` | Contract test passed | Windows query returned `\\.\\DISPLAY1`, 1536x960, primary | PASS |
| Window bounds/focus/min/max state | Native Win32 query | Covered by discovery contract | Live query returned bounds and focused ChatGPT window | PASS |
| Codex detection/launch | Process-backed adapter | Truthfulness tests passed | ChatGPT process detected; Codex CLI not detected | PARTIAL / unavailable control transport |
| Cursor detection/launch | Process-backed adapter | Truthfulness tests passed | Not installed/detected | UNAVAILABLE |
| Antigravity detection/launch | Process-backed adapter | Truthfulness tests passed | Not installed/detected | UNAVAILABLE |
| Prompt sending/response observation | Explicit capability contract | Unavailable-path test passed | Not executed because no supported transport | UNAVAILABLE |
| Multi-agent orchestration | Isolated workspaces and persisted state | 10 orchestration tests passed | No live three-agent run | PARTIAL |
| Voice | Existing voice pipeline | Existing focused tests | Hardware acceptance not run | ENVIRONMENT-DEPENDENT |
| Vision | Existing vision pipeline | Existing focused tests | Camera/model acceptance not run | ENVIRONMENT-DEPENDENT |

Live adapter diagnostics on 2026-09-19 reported Cursor and Codex processes running and launch commands discoverable, but `send_prompt`, response observation, waiting detection, and completion detection are explicitly `false`. Antigravity was not detected. This is detection evidence only; it is not a live multi-agent success claim.

## Controlled Codex live demonstration

- Workspace: isolated temporary Git repository under the Windows temp directory.
- Prompt: non-destructive connectivity check explicitly forbidding file changes.
- Delivery: `codex exec` accepted the prompt and returned a verified child PID.
- Observation: JSONL output was captured; final state was `COMPLETED` with exit code `0`.
- Result: Codex returned `READY`; no files were created, modified, or deleted.
- Configuration warnings: the user Codex profile contains two ignored deprecated settings; they did not prevent this run.

## Live Windows evidence

Command executed from the repository:

```text
.venv\Scripts\python.exe -c "... DesktopConnector().list_monitors()/list_windows() ..."
```

Observed: Windows platform `win32`; one primary monitor; eight visible top-level windows. Records included native handle, PID, executable path where permitted, title, x/y/width/height, visibility, minimized/maximized state, focus state, and monitor ID. No window was moved or closed during this acceptance check.

The live evidence proves resource discovery, not external-agent prompt delivery. Codex/Cursor/Antigravity are not reported as controllable until a real supported CLI/API/UI Automation transport is detected.
