import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Eye, Keyboard, MonitorUp, MousePointer2, Play, RefreshCw, ShieldAlert } from "lucide-react";
import { nexoraApi } from "../../../api/client";
import { useNexora } from "../../../context/NexoraContext";

type ConnectorInfo = { name: string; health: string; capabilities: string[] };

export function ComputerControlPage() {
  const { events, connected } = useNexora();
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [automation, setAutomation] = useState<{ registered_actions: string[]; history: Array<Record<string, unknown>> }>({ registered_actions: [], history: [] });
  const [mouseState, setMouseState] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [connectorData, automationData, mouse] = await Promise.all([
        nexoraApi.connectors(),
        nexoraApi.automation(),
        nexoraApi.visionMouseState().catch((e) => ({ ok: false, error: e instanceof Error ? e.message : String(e) })),
      ]);
      setConnectors(connectorData.connectors ?? []);
      setAutomation(automationData);
      setMouseState(mouse);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const computerEvents = useMemo(
    () => events.filter((event) =>
      event.topic.startsWith("automation.") ||
      event.topic.startsWith("security.") ||
      event.topic.startsWith("vision.") ||
      event.topic.startsWith("agent.") ||
      event.topic.startsWith("orchestrator."),
    ).slice(-24).reverse(),
    [events],
  );

  const availableConnectors = connectors.filter((connector) => connector.health === "AVAILABLE" || connector.health === "DEGRADED");

  const runAutomation = async (action: string) => {
    setError("");
    try {
      await nexoraApi.automationRun(action);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="g-page">
      <section className="g-page-hero">
        <div>
          <p className="g-eyebrow">Computer Control</p>
          <h1>Windows actions, connectors, mouse state, and automation evidence.</h1>
          <p>G can only show and run capabilities that the backend reports. If a connector is unavailable, this page says so.</p>
        </div>
        <button onClick={refresh} disabled={loading} className="g-secondary-action">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </section>

      {error && (
        <div className="g-empty-inline" role="alert">
          <ShieldAlert className="h-5 w-5" />
          <p>{error}</p>
        </div>
      )}

      <section className="g-card-grid g-card-grid-three">
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><MonitorUp className="h-4 w-4" /></span></div>
          <h2>Connectors</h2>
          <p>{availableConnectors.length}/{connectors.length} available</p>
          <small>{connected ? "Runtime connected" : "Runtime offline"}</small>
        </article>
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><Keyboard className="h-4 w-4" /></span></div>
          <h2>Automation</h2>
          <p>{automation.registered_actions.length} registered actions</p>
          <small>{automation.history.length} history records</small>
        </article>
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><MousePointer2 className="h-4 w-4" /></span></div>
          <h2>Mouse / vision control</h2>
          <p>{String(mouseState.status ?? mouseState.state ?? mouseState.ok ?? "not available")}</p>
          <small>{String(mouseState.error ?? "Backend state returned")}</small>
        </article>
      </section>

      <section className="g-split-layout">
        <div className="g-panel">
          <div className="g-section-heading">
            <span>Action registry</span>
            <small>{automation.registered_actions.length} real actions</small>
          </div>
          {automation.registered_actions.length === 0 ? (
            <div className="g-empty-inline">
              <Keyboard className="h-6 w-6" />
              <p>No automation actions are registered.</p>
            </div>
          ) : (
            <div className="g-action-list">
              {automation.registered_actions.slice(0, 18).map((action) => (
                <button key={action} onClick={() => runAutomation(action)} className="g-action-row">
                  <span><Play className="h-4 w-4" /> {action}</span>
                  <small>Run</small>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="g-panel">
          <div className="g-section-heading">
            <span>Control timeline</span>
            <small>{computerEvents.length} events</small>
          </div>
          {computerEvents.length === 0 ? (
            <div className="g-empty-inline">
              <Eye className="h-6 w-6" />
              <p>No computer-control events have appeared in the event stream yet.</p>
            </div>
          ) : (
            <div className="g-event-list">
              {computerEvents.map((event) => (
                <div key={event.sequence}>
                  <span>#{event.sequence}</span>
                  <strong>{event.topic}</strong>
                  <small>{JSON.stringify(event.payload).slice(0, 140)}</small>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="g-panel">
        <div className="g-section-heading">
          <span>Connector capabilities</span>
          <small>{connectors.length} connectors</small>
        </div>
        <div className="g-card-grid g-card-grid-three">
          {connectors.map((connector) => (
            <article key={connector.name} className="g-system-card">
              <h2>{connector.name}</h2>
              <p>{connector.health}</p>
              <small>{connector.capabilities.join(", ") || "No capabilities returned"}</small>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
