import React, { useMemo, useState } from "react";
import { ArrowUpRight, Bot, Brain, Database, Mic, Network, Send, ShieldCheck, Volume2, Workflow } from "lucide-react";
import { useNexora } from "../../../context/NexoraContext";

const quickLinks = [
  { tab: "brain", label: "Brain Core", icon: Brain },
  { tab: "pet-g", label: "Pet G", icon: Bot },
  { tab: "knowledge", label: "Knowledge", icon: Network },
  { tab: "memory", label: "Memory", icon: Database },
  { tab: "workflows", label: "Workflows", icon: Workflow },
  { tab: "connectors", label: "Connectors", icon: ShieldCheck },
];

function metric(value?: number, suffix = "") {
  return typeof value === "number" ? `${value.toFixed(0)}${suffix}` : "--";
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
    ? "Offline"
    : busy
      ? "Processing"
      : voiceState !== "idle"
        ? voiceState.replaceAll("_", " ")
        : brainState?.stage?.replaceAll("_", " ") || "Standby";

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
    <div className="g-page dashboard-redesign">
      <section className="g-hero-panel" aria-labelledby="dashboard-title">
        <div className="g-hero-copy">
          <span className="g-eyebrow">G / LOCAL COGNITIVE OPERATING SYSTEM</span>
          <h1 id="dashboard-title">Command the whole machine from one calm deck.</h1>
          <p>
            Live backend state, memory, learning, orchestration, voice, vision and your new Pet G companion stay in one
            workspace. No fake telemetry, no decorative placeholders.
          </p>
        </div>
        <div className="g-hero-status">
          <span className={connected ? "g-live-dot" : "g-live-dot is-offline"} />
          <strong>{phase}</strong>
          <small>{connected ? "Runtime linked" : "Start backend runtime"}</small>
        </div>
      </section>

      <section className="g-metric-grid" aria-label="Runtime metrics">
        <article>
          <span>CPU</span>
          <strong>{connected ? metric(status?.cpu, "%") : "--"}</strong>
        </article>
        <article>
          <span>Memory</span>
          <strong>{connected ? metric(status?.ram, "%") : "--"}</strong>
        </article>
        <article>
          <span>Events/sec</span>
          <strong>{connected ? (status?.events_per_sec ?? 0).toFixed(1) : "--"}</strong>
        </article>
        <article>
          <span>Modules</span>
          <strong>{connected ? `${healthyModules}/${modules.length || 0}` : "--"}</strong>
        </article>
      </section>

      <section className="g-dashboard-grid">
        <div className="g-panel command-panel">
          <div className="g-panel-title">
            <Brain size={17} />
            Command Line
          </div>
          <div className="g-response" role="status">
            <span>G replied</span>
            <p>{lastMessage}</p>
          </div>
          {(error || localError) && <p role="alert" className="g-alert">{error || localError}</p>}
          <form onSubmit={submit} className="g-command-form">
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
              <Mic size={18} />
            </button>
            <input
              aria-label="Command G"
              value={command}
              onChange={(event) => setCommand(event.target.value)}
              placeholder="Ask G to inspect, launch, learn, explain, or operate..."
              disabled={!connected}
            />
            <button type="button" aria-label="Speak responses" aria-pressed={spoken} className={spoken ? "is-selected" : ""} onClick={() => setSpoken(!spoken)}>
              <Volume2 size={18} />
            </button>
            <button type="submit" aria-label="Send command" disabled={!connected || busy || !command.trim()}>
              <Send size={18} />
            </button>
          </form>
        </div>

        <div className="g-panel">
          <div className="g-panel-title">
            <ShieldCheck size={17} />
            Current Objective
          </div>
          <p className="g-objective">{connected ? brainState?.current_goal || "No task is currently running." : "Runtime unavailable."}</p>
          <dl className="g-facts">
            <div>
              <dt>Capability</dt>
              <dd>{connected ? brainState?.selected_capability || "None selected" : "--"}</dd>
            </div>
            <div>
              <dt>Verification</dt>
              <dd>{connected ? cognitionState?.last_monitor?.verification_succeeded ? "Verified" : "Not verified" : "--"}</dd>
            </div>
          </dl>
        </div>

        <div className="g-panel">
          <div className="g-panel-title">
            <Network size={17} />
            Event Stream
          </div>
          <div className="g-event-list">
            {connected && events.length ? (
              events.slice(-5).reverse().map((event) => (
                <div key={event.sequence}>
                  <span>#{event.sequence}</span>
                  <p>{event.topic}</p>
                </div>
              ))
            ) : (
              <p className="muted">Waiting for runtime events.</p>
            )}
          </div>
        </div>
      </section>

      <section className="g-quick-grid" aria-label="Primary workspaces">
        {quickLinks.map((link) => {
          const Icon = link.icon;
          return (
            <button key={link.tab} type="button" onClick={() => onNavigate?.(link.tab)}>
              <Icon size={18} />
              <span>{link.label}</span>
              <ArrowUpRight size={15} />
            </button>
          );
        })}
      </section>
    </div>
  );
}
