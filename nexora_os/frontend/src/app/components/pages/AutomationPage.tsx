import React, { useEffect, useState } from "react";
import { History, Play, Settings2, Wand2 } from "lucide-react";
import { nexoraApi } from "../../../api/client";

export function AutomationPage() {
  const [actions, setActions] = useState<string[]>([]);
  const [history, setHistory] = useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await nexoraApi.automation();
      setActions(data.registered_actions ?? []);
      setHistory(data.history ?? []);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Automation service unavailable");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh().catch(() => undefined); }, []);

  const run = async (action: string) => {
    await nexoraApi.automationRun(action);
    await refresh();
  };

  return (
    <div className="g-page">
      <section className="g-page-hero">
        <div>
          <p className="g-eyebrow">Automation</p>
          <h1>Local actions with visible audit trails.</h1>
          <p>Only registered actions from the backend are executable here. No fake shortcuts, no phantom workflows.</p>
        </div>
        <button onClick={() => refresh()} className="g-secondary-action">
          <Settings2 className="h-4 w-4" />
          Refresh registry
        </button>
      </section>

      {error && <div className="g-alert-panel">{error}</div>}

      <section className="g-split-layout">
        <div className="g-panel">
          <div className="g-section-heading">
            <span>Action registry</span>
            <small>{loading ? "Loading" : `${actions.length} available`}</small>
          </div>
          {actions.length === 0 ? (
            <div className="g-empty-inline">
              <Wand2 className="h-6 w-6" />
              <p>{loading ? "Reading automation registry…" : "No registered local actions yet."}</p>
            </div>
          ) : (
            <div className="g-action-list">
              {actions.map((action) => (
                <button key={action} onClick={() => run(action)} className="g-action-row">
                  <span><Play className="h-4 w-4" /> {action}</span>
                  <small>Run</small>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="g-panel">
          <div className="g-section-heading">
            <span>Execution history</span>
            <small>{history.length} records</small>
          </div>
          {history.length === 0 ? (
            <div className="g-empty-inline">
              <History className="h-6 w-6" />
              <p>Run an action to create the first history entry.</p>
            </div>
          ) : (
            <div className="g-history-stack">
              {history.slice().reverse().map((entry, index) => (
                <pre key={index}>{JSON.stringify(entry, null, 2)}</pre>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
