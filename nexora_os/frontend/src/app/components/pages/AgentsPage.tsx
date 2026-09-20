import React, { useState } from "react";
import { Activity, Bot, CheckCircle2, Clock3, Cpu, Play, ShieldAlert } from "lucide-react";
import { nexoraApi } from "../../../api/client";
import { useNexora } from "../../../context/NexoraContext";

type RuntimeAgent = {
  name: string;
  status: string;
  queued?: number;
  completed?: number;
  failed?: number;
};

function statusClass(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("ready") || normalized.includes("idle") || normalized.includes("online")) return "g-status-good";
  if (normalized.includes("fail") || normalized.includes("error")) return "g-status-bad";
  return "g-status-warn";
}

export function AgentsPage() {
  const { agents, connected } = useNexora();
  const [result, setResult] = useState("");
  const runtimeAgents = (agents.runtime as RuntimeAgent[]) ?? [];
  const totals = runtimeAgents.reduce(
    (acc, agent) => ({
      queued: acc.queued + (agent.queued ?? 0),
      completed: acc.completed + (agent.completed ?? 0),
      failed: acc.failed + (agent.failed ?? 0),
    }),
    { queued: 0, completed: 0, failed: 0 },
  );

  const run = async (name: string) => {
    const response = await nexoraApi.agentTask(name, { input: `Health check requested for ${name}` });
    setResult(JSON.stringify(response, null, 2));
  };

  return (
    <div className="g-page">
      <section className="g-page-hero">
        <div>
          <p className="g-eyebrow">Agent Runtime</p>
          <h1>Workers, queues, and delegated intelligence.</h1>
          <p>
            Every agent card is tied to the live runtime state. Queue a health task only when the backend is connected.
          </p>
        </div>
        <div className="g-hero-actions">
          <span className={`g-live-pill ${connected ? "g-status-good" : "g-status-warn"}`}>
            <Activity className="h-3.5 w-3.5" />
            {connected ? "Runtime linked" : "Runtime offline"}
          </span>
        </div>
      </section>

      <section className="g-metric-strip">
        <article>
          <Clock3 className="h-4 w-4" />
          <span>Queued</span>
          <strong>{totals.queued}</strong>
        </article>
        <article>
          <CheckCircle2 className="h-4 w-4" />
          <span>Completed</span>
          <strong>{totals.completed}</strong>
        </article>
        <article>
          <ShieldAlert className="h-4 w-4" />
          <span>Failed</span>
          <strong>{totals.failed}</strong>
        </article>
      </section>

      {runtimeAgents.length === 0 ? (
        <div className="g-empty-state">
          <Bot className="h-8 w-8" />
          <h2>No runtime agents reported yet.</h2>
          <p>Start the backend runtime and this page will populate with registered workers.</p>
        </div>
      ) : (
        <section className="g-card-grid">
          {runtimeAgents.map((agent) => (
            <article key={agent.name} className="g-system-card">
              <div className="g-card-topline">
                <span className="g-card-icon"><Cpu className="h-4 w-4" /></span>
                <span className={`g-status-dot ${statusClass(agent.status)}`}>{agent.status}</span>
              </div>
              <h2>{agent.name}</h2>
              <p>Queue depth {agent.queued ?? 0}; completed {agent.completed ?? 0}; failed {agent.failed ?? 0}.</p>
              <button disabled={!connected} onClick={() => run(agent.name)} className="g-primary-action">
                <Play className="h-4 w-4" />
                Queue health task
              </button>
            </article>
          ))}
        </section>
      )}

      {result && (
        <section className="g-code-panel" aria-label="Latest agent task result">
          <div className="g-section-heading">
            <span>Latest task response</span>
            <small>JSON payload</small>
          </div>
          <pre>{result}</pre>
        </section>
      )}
    </div>
  );
}
