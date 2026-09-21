import React, { useMemo, useState } from "react";
import { Activity, AlertTriangle, Brain, Bug, Database, RefreshCw, TerminalSquare } from "lucide-react";
import { nexoraApi } from "../../../api/client";
import { useNexora } from "../../../context/NexoraContext";

export function DeveloperPage() {
  const { connected, events, status, brainState, cognitionState, modules, gCoreState } = useNexora();
  const [apiSnapshot, setApiSnapshot] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const eventGroups = useMemo(() => {
    const groups: Record<string, number> = {};
    for (const event of events) {
      const prefix = event.topic.split(".")[0] || "runtime";
      groups[prefix] = (groups[prefix] ?? 0) + 1;
    }
    return Object.entries(groups).sort((a, b) => b[1] - a[1]);
  }, [events]);

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const [health, state, capabilities, security] = await Promise.all([
        nexoraApi.health(),
        nexoraApi.state(),
        nexoraApi.capabilities(),
        nexoraApi.securityStatus(),
      ]);
      setApiSnapshot({ health, state, capabilities, security });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="g-page">
      <section className="g-page-hero">
        <div>
          <p className="g-eyebrow">Developer Mode</p>
          <h1>Live runtime evidence for debugging G.</h1>
          <p>Events, state snapshots, modules, capabilities, and errors are shown from the backend contract. Nothing here is a fake console.</p>
        </div>
        <button onClick={refresh} disabled={loading} className="g-secondary-action">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Probe APIs
        </button>
      </section>

      {error && (
        <div className="g-empty-inline" role="alert">
          <AlertTriangle className="h-5 w-5" />
          <p>{error}</p>
        </div>
      )}

      <section className="g-card-grid g-card-grid-three">
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><Activity className="h-4 w-4" /></span></div>
          <h2>Connection</h2>
          <p>{connected ? "WebSocket stream is connected." : "Backend stream unavailable."}</p>
          <span className={`g-live-pill ${connected ? "g-status-good" : "g-status-warn"}`}>{connected ? "LIVE" : "OFFLINE"}</span>
        </article>
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><Brain className="h-4 w-4" /></span></div>
          <h2>G Core</h2>
          <p>{gCoreState}</p>
          <small>{brainState?.current_goal || "No active goal."}</small>
        </article>
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><Database className="h-4 w-4" /></span></div>
          <h2>Runtime</h2>
          <p>{events.length} recent events · {modules.length} modules</p>
          <small>CPU {Math.round(status?.cpu ?? 0)}% · RAM {Math.round(status?.ram ?? 0)}%</small>
        </article>
      </section>

      <section className="g-split-layout">
        <div className="g-panel">
          <div className="g-section-heading">
            <span>Event stream</span>
            <small>{events.length} retained</small>
          </div>
          {events.length === 0 ? (
            <div className="g-empty-inline">
              <TerminalSquare className="h-6 w-6" />
              <p>No events have reached the frontend yet.</p>
            </div>
          ) : (
            <div className="g-event-list">
              {events.slice(-24).reverse().map((event) => (
                <div key={event.sequence}>
                  <span>#{event.sequence}</span>
                  <strong>{event.topic}</strong>
                  <small>{JSON.stringify(event.payload).slice(0, 140)}</small>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="g-panel">
          <div className="g-section-heading">
            <span>Diagnostics</span>
            <small>{eventGroups.length} event groups</small>
          </div>
          <div className="g-card-grid">
            {eventGroups.map(([name, count]) => (
              <article key={name} className="g-system-card">
                <h2>{name}</h2>
                <p>{count} events</p>
              </article>
            ))}
          </div>
          <div className="g-code-panel">
            <div className="g-section-heading">
              <span><Bug className="h-4 w-4" /> API probe</span>
              <small>{Object.keys(apiSnapshot).length ? "loaded" : "not run"}</small>
            </div>
            <pre>{JSON.stringify({ brainState, cognitionState, apiSnapshot }, null, 2)}</pre>
          </div>
        </div>
      </section>
    </div>
  );
}
