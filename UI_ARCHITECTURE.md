# G UI Architecture

Generated: 2026-09-21

## Product Direction

G is a Windows-style cognitive operating environment, not a generic dashboard. The frontend should remain a realtime visualization and command layer over the actual backend.

## Shell Layout

- Top: compact command/status strip with backend connection, current G Core state, model/goal context, and context-panel toggle.
- Left: compact lens rail and grouped lens map.
- Center: dominant cognitive workspace with spatial 3D background and the active lens.
- Right: intelligence/context drawer for runtime, brain, cognition, modules, and recent work.
- Bottom: compact floating dock for primary lenses; command entry lives inside Home/Chat and should converge into a universal bottom command bar.

## State Boundaries

- `NexoraProvider` owns backend state and realtime event subscription.
- UI-only state stays local to pages/components.
- Backend state is not duplicated if it can be read directly from context.
- `GCoreState` is the semantic bridge between backend events and 3D/2D presence visuals.

## Event-Driven Visuals

- `CognitiveCore3D` consumes `gCoreState`.
- `NeuralNetwork` consumes real agents, workflows, and recent event topics.
- Page-level status labels should migrate from raw `busy` checks to `gCoreState` where appropriate.
- Pet G should consume the same state to switch idle/listen/think/speak/error/celebrate moods.

## Design System Direction

- Primary background: near-black spatial environment.
- Panels: dark glass surfaces with restrained blur.
- Accent: cyan/blue for live intelligence, amber for execution/attention, green for success, red for error.
- Typography: modern sans-serif with compact hierarchy.
- Motion: purposeful, event-driven, reduced-motion aware.

## Component Primitives To Standardize

- `GlassPanel`
- `StatusBadge`
- `CommandBar`
- `Orb`
- `AgentNode`
- `WorkflowNode`
- `MemoryNode`
- `KnowledgeNode`
- `Inspector`
- `Timeline`
- `Waveform`
- `Graph`
- `Toast`
- `Tooltip`
- `ContextMenu`

## Navigation Target

```text
G
├── Cognitive Space / Home
├── Conversation
├── Agents
├── Workflows
├── Memory
├── Knowledge
├── Vision
├── Voice
├── Computer Control
├── MCP
├── Plugins
├── Learning
├── 3D Companion / Pet G
├── Security
├── System
└── Developer
```

## Current Implementation Status

- Implemented now:
  - G2 app shell
  - realtime context provider
  - WebSocket bootstrap and updates
  - 3D cognitive core and neural network
  - Pet G page/model package
  - workflow studio
  - memory/knowledge/voice/vision/agents/automation/connectors/settings/lab pages
  - Learning lens backed by `/learning/jobs`
  - MCP lens backed by `/mcp/status` and `/mcp/tools`
  - Plugin lens backed by `/plugins` with truthful "registry unavailable" state
  - Security lens backed by `/security/status`, `/security/audit`, and emergency-stop controls
  - `GCoreState` event mapping from backend topics
- Needs follow-up:
  - developer event/log lens
  - computer-control timeline
  - reduced-motion control for WebGL/heavy effects
  - lazy loading for heavy lenses and 3D
  - lint/test script setup

## Cleanup Policy

- Delete only verified duplicate/dead UI after the replacement page is connected and production build passes.
- Do not remove backend APIs, memory, voice, vision, workflow, MCP, plugin, automation, or computer-control functionality during UI cleanup.
- Keep stale or unavailable capability surfaces honest by showing unavailable/offline states.

## Performance Plan

- Keep the center 3D scene lightweight and instanced.
- Avoid rendering hundreds of heavyweight React agent components.
- Lazy-load workflow, 3D companion, vision, and developer lenses.
- Throttle high-frequency event rendering and keep event history bounded.
- Dispose Three.js geometries/materials when dynamically replacing resources.
- Add reduced-motion and low-power rendering modes.
