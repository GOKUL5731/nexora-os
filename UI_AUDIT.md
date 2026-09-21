# G UI Audit

Generated: 2026-09-21

## Existing Frontend

- Framework: React 18 + TypeScript + Vite.
- Styling: project CSS files under `nexora_os/frontend/src/styles`, with the active G2 shell in `custom.css`.
- 3D stack: Three.js, React Three Fiber, Drei, postprocessing package installed.
- Workflow stack: `@xyflow/react` is installed and used by `WorkflowStudio`.
- Runtime state: `NexoraProvider` connects to `/ws/events`, stores backend status/state/events, and exposes command, voice, memory, vision, companion, connector, and workflow API actions.

## Active Pages And Lenses

- Home / dashboard: `DashboardPage.tsx`
- Conversation: `ChatPage.tsx`
- Brain: `BrainView.tsx`
- Memory: `MemoryPage.tsx`
- Knowledge: `KnowledgePage.tsx`
- Projects / orchestration: `ProjectsPage.tsx`
- Agents: `AgentsPage.tsx`
- Workflows: `WorkflowStudio.tsx`
- Automation: `AutomationPage.tsx`
- Vision: `VisionPage.tsx`
- Voice: `VoicePage.tsx`
- Connectors / computer links: `ConnectorsPage.tsx`
- AI Lab: `LabPage.tsx`
- Settings: `SettingsPage.tsx`
- Companion: `CompanionPage.tsx`
- Pet G: `PetGPage.tsx`
- Learning: `LearningPage.tsx`
- MCP center: `MCPPage.tsx`
- Plugin center: `PluginsPage.tsx`
- Security: `SecurityPage.tsx`
- Computer Control: `ComputerControlPage.tsx`
- Developer Mode: `DeveloperPage.tsx`

## Useful Components To Preserve

- `NexoraContext.tsx`: real backend/WebSocket integration layer.
- `Scene3D.tsx`, `CognitiveCore3D.tsx`, `NeuralNetwork.tsx`, `PetGStage.tsx`, `PetGModel.tsx`: current spatial/companion foundation.
- `WorkflowStudio.tsx`: existing visual workflow editor.
- `RightPanel.tsx`: current context/intelligence surface.
- `CommandBar.tsx`, `DashboardPage.tsx`, `ChatPage.tsx`: command surfaces that already call `/process` instead of fake local responses.

## Duplicate Or Legacy UI

- `TopBar.tsx`, `Sidebar.tsx`, `LowerPanels.tsx`, and `CognitiveOrb.tsx` are legacy Command Center components. They are still useful references, but the active shell in `App.tsx` now uses the G2 command strip, lens map, floating dock, and right context drawer.
- Multiple style files exist: `custom.css`, `jarvis.css`, `theme.css`, `tailwind.css`, `index.css`, `fonts.css`. `custom.css` is the active redesign layer; older styles should be consolidated only after verifying every page still renders.
- No backend functionality should be removed while cleaning these UI layers.

## Backend Endpoints Identified

- Core/system: `GET /status`, `/health`, `/state`, `/events`, `/settings`
- Brain/cognition: `GET /brain/status`, `/cognition/status`, `POST /cognition/perceive`
- Capabilities/security: `GET /capabilities`, `/security/status`, `POST /security/emergency-stop`, `/security/emergency-stop/clear`
- Security audit: `GET /security/audit`
- Agents/AI Lab: `GET /agents`, `/tools`, `/agents/generated`, `/ai_lab/status`, `POST /agents/{name}/tasks`, `/agents/build`, `/ai_lab/validate`
- Memory: `GET /memory`, `/memory/search`, `/memory/network`, `/memory/episodes`, `/memory/procedures`, `POST /memory/store`, `/memory/reflect`, `/memory/episodes`, `/memory/procedures`, `/memory/procedures/{id}/score`
- Knowledge/learning: `GET /knowledge`, `/knowledge/search`, `/knowledge/graph`, `/learning/jobs`, `/learning/jobs/{id}`, `POST /knowledge/learn/{domain}`, `/knowledge/index`, `/learning/jobs`
- Workflows: `GET /workflows`, `/workflows/graphs`, `/workflows/graph/{name}`, `/workflows/trace/{name}`, `/platform/node-types`, `POST /workflows/graph/save`, `/workflows/graph/run/{name}`, `/workflows/generate`
- Voice: `GET /voice/status`, `POST /voice/listen`, `/voice/speak`
- Vision: `GET /vision/status`, `/vision/mouse/state`, `/vision/gestures/state`, `POST /vision/webcam/start`, `/vision/webcam/stop`, `/vision/capture`, `/vision/frame`, `/vision/frame/mouse`, `/vision/mouse/enable`, `/vision/mouse/disable`, `/vision/screen`, `/vision/gestures/enable`, `/vision/gestures/disable`, `/vision/gestures/capture`
- Automation/connectors/computer control: `GET /automation`, `/connectors`, `POST /automation/run`, `/connectors/{name}/execute`
- MCP/plugin: `GET /mcp/status`, `/mcp/tools`, `/plugins`
- Realtime/companion: `GET /realtime/livekit/status`, `/companion/status`, `POST /realtime/livekit/token`, `/companion/pair`, `/companion/sync`
- WebSocket: `/ws/events`

## WebSocket Events Identified

The backend publishes real event topics including:

- `runtime.started`, `runtime.stopped`, `runtime.progress`, `runtime.response`
- `brain.state.changed`, `brain.decision`, `step.started`, `step.completed`, `step.failed`
- `agent.queued`, `agent.started`, `agent.step`, `agent.ask_user`, `agent.completed`, `agent.failed`, `agent.recovered`
- `voice.activity`, `voice.utterance`, `voice.transcript`, `voice.status`, `voice.error`, `voice.listening_started`, `voice.listening_stopped`, `voice.tts_started`, `voice.tts_chunk`, `voice.tts_done`
- `vision.updated`
- `workflow.saved`, `workflow.node`, `workflow.notification`, `workflow.completed`, `workflow.failed`
- `memory.stored`, `memory.reflected`, `memory.episode_recorded`, `memory.procedure_upserted`, `memory.procedure_evaluated`
- `knowledge.domain.learned`
- `learning.job.created`, `learning.job.started`, `learning.job.completed`, `learning.job.failed`
- `automation.executed`
- `mcp.server_connected`
- `security.permission_denied`, `security.emergency_stop`
- `companion.paired`, `companion.synced`
- `state.voice`, `state.vision`, and other `state.*` updates

## Missing Connections / Gaps

- MCP center now has a dedicated read-only frontend lens; connect/disconnect/test actions still need a safe backend mutation contract.
- Plugin center now has a dedicated truthful lens; a real plugin registry is still not exposed by the backend.
- Security UI now has a dedicated lens for health, emergency stop, and audit entries; richer permission prompts still need product flow integration.
- Computer-control visualization now has a dedicated lens with connectors, automation actions, vision mouse state, and control-related event timeline.
- Developer mode now has a dedicated lens with event stream grouping and explicit API probes.
- G Core previously inferred state from generic busy/voice values. It now has a `GCoreState` mapped from real WebSocket topics, but page-level labels should continue migrating to that state.
- Frontend package has no `lint` or `test` scripts yet, so the requested `npm run lint` and `npm test` gates cannot run until scripts/tooling are added.

## Recommended Architecture

- Keep the current single React/Vite app and continue replacing legacy Command Center pieces in place.
- Treat `NexoraContext` as the real backend-state boundary.
- Add a lightweight event semantic layer for UI states instead of scattering topic interpretation across pages.
- Use `/ws/events` as the primary realtime source and HTTP endpoints for explicit user actions.
- Keep all unavailable backend features visible as `NOT AVAILABLE` / `OFFLINE` with reason and action, never as mocked data.
- Consolidate the active design system into named CSS/component primitives before deleting legacy files.
- Lazy-load heavy lenses: 3D, workflows, vision, and developer mode.
