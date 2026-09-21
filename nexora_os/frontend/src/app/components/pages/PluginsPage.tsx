import React, { useCallback, useEffect, useState } from "react";
import { Boxes, Plug, RefreshCw, Wrench } from "lucide-react";
import { nexoraApi, PluginRegistryStatus } from "../../../api/client";

export function PluginsPage() {
  const [registry, setRegistry] = useState<PluginRegistryStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRegistry(await nexoraApi.plugins());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const connectors = registry?.connectors ?? [];
  const capabilities = registry?.capabilities ?? [];

  return (
    <div className="g-page">
      <section className="g-page-hero">
        <div>
          <p className="g-eyebrow">Plugin Center</p>
          <h1>Installed plugins, connectors, and capability truth.</h1>
          <p>This runtime currently exposes connectors and capability registry data. It will not label connectors as installed plugins.</p>
        </div>
        <button onClick={refresh} disabled={loading} className="g-secondary-action">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </section>

      {error && <div className="g-empty-inline" role="alert"><Plug className="h-5 w-5" /><p>{error}</p></div>}

      <section className="g-card-grid g-card-grid-three">
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><Plug className="h-4 w-4" /></span></div>
          <h2>Plugin registry</h2>
          <p>{registry?.registry_available ? "Dedicated plugin registry available." : registry?.message || "Loading registry state."}</p>
          <span className={`g-live-pill ${registry?.registry_available ? "g-status-good" : "g-status-warn"}`}>
            {registry?.registry_available ? "AVAILABLE" : "NOT AVAILABLE"}
          </span>
        </article>
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><Boxes className="h-4 w-4" /></span></div>
          <h2>Connectors</h2>
          <p>{connectors.length} connector surfaces reported by backend.</p>
        </article>
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><Wrench className="h-4 w-4" /></span></div>
          <h2>Capabilities</h2>
          <p>{capabilities.length} registered capability records.</p>
        </article>
      </section>

      <section className="g-panel">
        <div className="g-section-heading">
          <span>Connector-backed ecosystem</span>
          <small>{connectors.length} visible</small>
        </div>
        {connectors.length === 0 ? (
          <div className="g-empty-inline">
            <Boxes className="h-6 w-6" />
            <p>No connectors reported. Backend may still be initializing.</p>
          </div>
        ) : (
          <div className="g-card-grid g-card-grid-three">
            {connectors.map((connector) => (
              <article key={connector.name} className="g-system-card">
                <h2>{connector.name}</h2>
                <p>{connector.health}</p>
                <small>{connector.capabilities.join(", ") || "No capabilities returned"}</small>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
