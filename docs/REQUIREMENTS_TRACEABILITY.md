# G Requirements Traceability

Audit basis: the pasted G Complete Build Master Prompt and the current repository state.

This is an evidence ledger, not a claim that the full G product is complete. A requirement is `VERIFIED` only when an executable check proves the behavior.

| ID | Requirement | Component | Status | Tests | Evidence |
|---|---|---|---|---|---|
| G-001 | Repository audit and implementation tracking exist | `docs/` | IMPLEMENTED | documentation review | `docs/CURRENT_SYSTEM_AUDIT.md`, `docs/IMPLEMENTATION_PLAN.md` |
| G-002 | Typed asynchronous event delivery | `nexora_os/backend/core/event_bus.py` | IN_PROGRESS | `test_core_runtime.py`, `test_event_bus_recovery.py` | Focused tests are present; full suite still being revalidated |
| G-003 | Runtime lifecycle and graceful shutdown | `nexora_os/backend/core/runtime.py` | IN_PROGRESS | `test_core_runtime.py` | Runtime implementation and lifecycle tests exist |
| G-004 | Fast/task conversation routing | `nexora_os/backend/brain/` | IMPLEMENTED | `test_conversation_routing.py` | Routing tests cover simple and task paths |
| G-005 | Memory persistence and retrieval | `nexora_os/backend/memory/` | IMPLEMENTED | memory/integration tests | Engine and conversation memory are present; broader verification remains |
| G-006 | Workflow execution truthfulness | `nexora_os/backend/workflows/` | IN_PROGRESS | workflow integration tests | Failure/result handling is under active stabilization |
| G-007 | Safe multi-agent workspace isolation | `nexora_os/backend/orchestration/` | IN_PROGRESS | `test_orchestration.py` | Worktree manager exists; async test execution was previously blocked by missing plugin |
| G-008 | Real health/degraded states | `nexora_os/backend/core/health_monitor.py` | IMPLEMENTED | `test_monitor_truthfulness.py` | Truthfulness tests exist; live optional hardware remains environment-dependent |
| G-009 | One-click Windows startup | `run_project.cmd`, `NEXORA_ONE_CLICK.cmd` | IN_PROGRESS | launcher smoke check | Launcher chain exists; end-to-end UI startup requires runtime verification |
| G-010 | Full multimodal G acceptance scenario | orchestration, adapters, UI | NOT_STARTED | none | No executable evidence for the complete live scenario yet |

## Current verification boundary

- `VERIFIED` is intentionally reserved for behavior with passing executable evidence.
- Hardware, external applications, credentials, and optional model providers must be reported as unavailable or blocked when they cannot be tested.
- Existing user changes in this checkout are preserved; this ledger is additive.
