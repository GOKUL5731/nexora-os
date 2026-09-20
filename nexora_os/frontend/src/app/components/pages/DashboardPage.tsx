import React, { useMemo, useState } from "react";
import {
  ArrowUpRight,
  Bot,
  Brain,
  Database,
  FolderGit2,
  Mic,
  Network,
  Send,
  Sparkles,
  Volume2,
  Workflow,
  Zap,
} from "lucide-react";
import { useNexora } from "../../../context/NexoraContext";

const intents = [
  { tab: "chat", label: "Talk to G", copy: "Ask, plan, inspect, or execute a local task.", icon: Sparkles },
  { tab: "pet-g", label: "Open Pet G", copy: "See the 3D companion and mood layer.", icon: Bot },
  { tab: "projects", label: "Build space", copy: "Track files, projects, and running work.", icon: FolderGit2 },
  { tab: "workflows", label: "Compose flows", copy: "Generate and run visual workflows.", icon: Workflow },
  { tab: "memory", label: "Recall memory", copy: "Inspect durable knowledge and events.", icon: Database },
  { tab: "agents", label: "Delegate", copy: "Check worker queues and agent health.", icon: Network },
];

function metric(value?: number, suffix = "") {
  return typeof value === "number" ? `${value.toFixed(0)}${suffix}` : "—";
}

export function DashboardPage({ onNavigate }: { onNavigate?: (tab: string) => void }) {
  const {
    connected,
    status,
    brainState,
    cognitionState,
    events,
    modules,
    voiceState,
    lastMessage,
    sendCommand,
    startVoice,
    busy,
    error,
  } = useNexora();
  const [command, setCommand] = useState("");
  const [spoken, setSpoken] = useState(false);
  const [localError, setLocalError] = useState("");

  const phase = !connected
    ? "Waiting for runtime"
    : busy
      ? "Thinking through task"
      : voiceState !== "idle"
        ? voiceState.replaceAll("_", " ")
        : brainState?.stage?.replaceAll("_", " ") || "Ready";

  const healthyModules = useMemo(
    () => modules.filter((module) => module.status === "online" || module.status === "running").length,
    [modules],
  );

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!command.trim() || busy || !connected) return;
    const result = await sendCommand(command, { speak: spoken });
    if (result) setCommand("");
  }

  return (
    <div className="g2-home">
      <section className="g2-home-hero" aria-labelledby="home-title">
        <div className="g2-home-copy">
          <span>G EXPERIENCE</span>
          <h1 id="home-title">Your computer, memory, agents, and Pet G in one living interface.</h1>
          <p>
            This is not a terminal dashboard. It is a spatial control layer for talking to G, opening lenses,
            checking truth from the runtime, and moving work forward.
          </p>
        </div>

        <div className="g2-presence-card">
          <div>
            <Brain className="h-5 w-5" />
            <span>{phase}</span>
          </div>
          <strong>{connected ? "G is linked to the local runtime." : "Start the backend to wake G fully."}</strong>
          <small>{brainState?.current_goal || "No active goal running."}</small>
        </div>
      </section>

      <section className="g2-ask-surface" aria-label="Ask G">
        <div className="g2-glyph-orb">
          <span>G</span>
        </div>
        <div className="g2-last-message">
          <small>Last response</small>
          <p>{lastMessage}</p>
          {(error || localError) && <strong role="alert">{error || localError}</strong>}
        </div>
        <form onSubmit={submit} className="g2-ask-form">
          <button
            type="button"
            aria-label="Listen through microphone"
            disabled={!connected || busy}
            onClick={async () => {
              setLocalError("");
              try {
                await startVoice();
              } catch (e) {
                setLocalError(e instanceof Error ? e.message : String(e));
              }
            }}
          >
            <Mic className="h-5 w-5" />
          </button>
          <input
            aria-label="Ask G"
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            placeholder={connected ? "Ask G to inspect, launch, remember, build, explain..." : "Runtime offline — start backend first"}
            disabled={!connected}
          />
          <button type="button" aria-label="Speak responses" aria-pressed={spoken} className={spoken ? "active" : ""} onClick={() => setSpoken(!spoken)}>
            <Volume2 className="h-5 w-5" />
          </button>
          <button type="submit" aria-label="Send command" disabled={!connected || busy || !command.trim()}>
            <Send className="h-5 w-5" />
          </button>
        </form>
      </section>

      <section className="g2-home-grid">
        <div className="g2-intent-board">
          {intents.map((intent) => {
            const Icon = intent.icon;
            return (
              <button key={intent.tab} onClick={() => onNavigate?.(intent.tab)}>
                <Icon className="h-5 w-5" />
                <span>{intent.label}</span>
                <p>{intent.copy}</p>
                <ArrowUpRight className="h-4 w-4" />
              </button>
            );
          })}
        </div>

        <div className="g2-truth-column">
          <article>
            <span><Zap className="h-4 w-4" /> Live proof</span>
            <dl>
              <div><dt>CPU</dt><dd>{connected ? metric(status?.cpu, "%") : "—"}</dd></div>
              <div><dt>RAM</dt><dd>{connected ? metric(status?.ram, "%") : "—"}</dd></div>
              <div><dt>Events</dt><dd>{connected ? (status?.events_per_sec ?? 0).toFixed(1) : "—"}</dd></div>
              <div><dt>Modules</dt><dd>{connected ? `${healthyModules}/${modules.length || 0}` : "—"}</dd></div>
            </dl>
          </article>
          <article>
            <span><Brain className="h-4 w-4" /> Current reasoning</span>
            <p>{connected ? brainState?.selected_capability || "No capability selected." : "Runtime unavailable."}</p>
            <small>{connected ? cognitionState?.last_monitor?.verification_succeeded ? "Last monitor verified" : "No verified monitor yet" : "Offline"}</small>
          </article>
          <article>
            <span><Network className="h-4 w-4" /> Fresh signals</span>
            {connected && events.length ? (
              events.slice(-4).reverse().map((event) => <p key={event.sequence}>#{event.sequence} {event.topic}</p>)
            ) : (
              <p>Waiting for runtime events.</p>
            )}
          </article>
        </div>
      </section>
    </div>
  );
}
