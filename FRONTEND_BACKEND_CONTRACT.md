# G Frontend / Backend Contract

Generated: 2026-09-21

## Runtime Base

- Frontend: `nexora_os/frontend`, React + Vite.
- Default API base: `VITE_NEXORA_API` or `http://127.0.0.1:7474` in dev.
- Production API base: `window.location.origin`.
- Realtime: WebSocket at `/ws/events`.

## Realtime Envelope

`/ws/events` sends:

```json
{
  "state": {},
  "events": [
    {
      "topic": "agent.started",
      "payload": {},
      "source": "PlannerAgent",
      "timestamp": 0,
      "sequence": 1,
      "priority": 1
    }
  ],
  "status": {}
}
```

UI consumer: `NexoraProvider`.

## G Core Event Mapping

| UI state | Current backend evidence |
| --- | --- |
| `OFFLINE` | WebSocket closed / backend unreachable |
| `STARTING` | WebSocket opened, `runtime.started`, `system.boot.started` |
| `IDLE` | connected with no active state |
| `LISTENING` | `voice.listening_started`, `voice.activity`, `status.voice_state` containing listening |
| `UNDERSTANDING` | `voice.utterance`, `voice.transcript`, command submitted |
| `THINKING` | `cognition.context.built`, `brain.decision`, local request in progress |
| `PLANNING` | `brain.state.changed` with stage `PLAN` |
| `EXECUTING` | `agent.started`, `agent.step`, `step.*`, `automation.*`, active `workflow.*` |
| `OBSERVING` | reserved for richer vision/computer-control observations |
| `VERIFYING` | `brain.state.changed` with stage `VERIFY`, `cognition.self_monitor` |
| `SPEAKING` | `voice.tts_started`, `voice.tts_chunk`, `voice.status=speaking` |
| `LEARNING` | `learning.*`, `knowledge.domain.learned`, `memory.*` |
| `VISION` | `vision.updated`, `state.vision` |
| `ERROR` | `*.failed`, `*.error`, `security.*`, `voice.error` |
| `SUCCESS` | `runtime.response`, `workflow.completed`, brain stage `COMPLETE` |

## HTTP Connections

| UI consumer | Method | Endpoint | Request | Response |
| --- | --- | --- | --- | --- |
| System top bar, Home, RightPanel | `GET` | `/status` | none | readiness, CPU, RAM, GPU, event rate, module/task counts |
| Developer/System lenses | `GET` | `/health` | none | startup and module health snapshot |
| Realtime bootstrap | `GET` | `/state` | none | event bus state snapshot |
| Brain lens | `GET` | `/brain/status` | none | stage, goal, plan, capability, model, verification |
| Cognitive status | `GET` | `/cognition/status` | none | identity, loop, monitor, memory and knowledge counts |
| Command surfaces | `POST` | `/process` | `{ input, context }` | process result, optional plan/task data |
| Command confirmation | `POST` | `/confirm` | `{ task_id, confirmed }` | confirmation result |
| Agents lens | `GET` | `/agents` | none | tool/runtime agents |
| Agent action | `POST` | `/agents/{name}/tasks` | `{ task }` | agent task result |
| Agent creation | `POST` | `/agents/build` | `{ name?, description }` | generated/registered agent or policy error |
| AI Lab | `GET` | `/ai_lab/status` | none | generated agents, LLM availability, creation policy |
| AI Lab validation | `POST` | `/ai_lab/validate` | `{ code }` | AST/security validation |
| Memory lens | `GET` | `/memory` | `query`, `limit` | count and memory items |
| Memory graph | `GET` | `/memory/network` | none | memory graph nodes/edges |
| Memory search | `GET` | `/memory/search` | `q`, `limit` | memory hits |
| Memory store | `POST` | `/memory/store` | `{ text, memory_type, tags }` | stored memory result |
| Knowledge lens | `GET` | `/knowledge` | none | knowledge status and domains |
| Knowledge graph | `GET` | `/knowledge/graph` | `node`, `limit` | knowledge graph |
| Knowledge search | `GET` | `/knowledge/search` | `q`, `domain`, `limit` | knowledge hits |
| Knowledge learn | `POST` | `/knowledge/learn/{domain}` | optional `web` query | learning/index result |
| Learning jobs | `GET` | `/learning/jobs` | `limit` | learning manager status and jobs |
| Learning job start | `POST` | `/learning/jobs` | `{ domain, goal, resources, expected_terms }` | job result |
| Workflows lens | `GET` | `/workflows`, `/workflows/graphs` | none | workflow summaries |
| Workflow editor | `GET` | `/workflows/graph/{name}` | path name | graph spec |
| Workflow editor | `POST` | `/workflows/graph/save` | graph spec | save result |
| Workflow editor | `POST` | `/workflows/graph/run/{name}` | path name | execution result |
| NL workflow creation | `POST` | `/workflows/generate` | `{ description }` | generated graph spec |
| Workflow trace | `GET` | `/workflows/trace/{name}` | optional `run_id` | trace steps |
| Voice lens | `GET` | `/voice/status` | none | STT/TTS/language status |
| Voice command | `POST` | `/voice/listen` | `timeout` query | transcript or error |
| Voice speak | `POST` | `/voice/speak` | `{ text, interrupt }` | TTS result |
| Vision lens | `GET` | `/vision/status` | none | camera/object/OCR health |
| Vision actions | `POST` | `/vision/webcam/start`, `/vision/webcam/stop`, `/vision/capture`, `/vision/frame`, `/vision/screen` | action-specific query/body | vision result |
| Computer control | `POST` | `/vision/mouse/enable`, `/vision/mouse/disable`, `/vision/frame/mouse` | none | mouse-control state/frame |
| Automation | `GET` | `/automation` | none | registered actions/history |
| Automation action | `POST` | `/automation/run` | `{ input, context }` | execution result |
| Connectors | `GET` | `/connectors` | none | connector health/capabilities |
| Connector action | `POST` | `/connectors/{name}/execute` | `{ input, context }` | connector result |
| Computer control | `GET` | `/vision/mouse/state`, `/connectors`, `/automation`, `/events` | none / `limit` | mouse-control status, connector capability state, automation history, control timeline |
| Developer mode | `GET` | `/events`, `/health`, `/state`, `/capabilities`, `/security/status` | none / `limit` | live event stream, runtime snapshots, capability inventory, security state |
| Security | `GET` | `/security/status` | none | emergency stop and health |
| Security audit | `GET` | `/security/audit` | `limit` | recent audited API requests |
| Security | `POST` | `/security/emergency-stop`, `/security/emergency-stop/clear` | reason / none | security state |
| MCP center | `GET` | `/mcp/status` | none | MCP manager health, connected server count, total tool count |
| MCP center | `GET` | `/mcp/tools` | none | connected MCP tool schemas |
| Plugin center | `GET` | `/plugins` | none | truthful plugin registry state, connector-backed ecosystem, capability registry |
| Companion | `GET` | `/companion/status` | none | paired devices and desktop status |
| Companion | `POST` | `/companion/pair`, `/companion/sync` | device/sync payload | pair/sync result |

## Contract Rules

- If a backend field is unavailable, UI must show `NOT AVAILABLE`, `OFFLINE`, or a concrete error reason.
- UI must not fabricate counts, progress, CPU/GPU values, installed plugins, MCP servers, agent status, learning status, or workflow completion.
- Long-running visuals must be driven by event topics or active HTTP requests, not fake timers.
- Backend errors must produce a user-visible failed/offline state.
- Accessibility/performance preferences such as low-power WebGL mode are local UI state and must not be represented as backend capability state.
