import React, { useCallback, useEffect, useState } from "react";
import { PlugZap, RefreshCw, ServerCog, Wrench } from "lucide-react";
import { MCPTool, nexoraApi } from "../../../api/client";

export function MCPPage() {
  const [status, setStatus] = useState<Record<string, unknown>>({});
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [mcpStatus, mcpTools] = await Promise.all([
        nexoraApi.mcpStatus(),
        nexoraApi.mcpTools(),
      ]);
      setStatus(mcpStatus);
      setTools(mcpTools.tools ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const connectedServers = Number(status.connected_servers ?? 0);
  const totalTools = Number(status.total_tools ?? tools.length);

  return (
    <div className="g-page">
      <section className="g-page-hero">
        <div>
          <p className="g-eyebrow">MCP Center</p>
          <h1>Connected MCP servers and tool schemas.</h1>
          <p>This view reads the local MCP manager. Empty means no MCP server is connected, not that tools are secretly available.</p>
        </div>
        <button onClick={refresh} disabled={loading} className="g-secondary-action">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </section>

      {error && <div className="g-empty-inline" role="alert"><PlugZap className="h-5 w-5" /><p>{error}</p></div>}

      <section className="g-card-grid g-card-grid-three">
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><ServerCog className="h-4 w-4" /></span></div>
          <h2>Manager</h2>
          <p>{String(status.status ?? "unknown")}</p>
        </article>
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><PlugZap className="h-4 w-4" /></span></div>
          <h2>Servers</h2>
          <p>{connectedServers} connected</p>
        </article>
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><Wrench className="h-4 w-4" /></span></div>
          <h2>Tools</h2>
          <p>{totalTools} available</p>
        </article>
      </section>

      <section className="g-panel">
        <div className="g-section-heading">
          <span>Tool schemas</span>
          <small>{tools.length} visible</small>
        </div>
        {tools.length === 0 ? (
          <div className="g-empty-inline">
            <PlugZap className="h-6 w-6" />
            <p>No MCP tools are connected. Connect an MCP server before using MCP actions.</p>
          </div>
        ) : (
          <div className="g-card-grid g-card-grid-three">
            {tools.map((tool, index) => (
              <article key={`${tool._server}-${tool.name}-${index}`} className="g-system-card">
                <h2>{tool.name || "Unnamed tool"}</h2>
                <p>{tool.description || "No description returned by server."}</p>
                <small>{tool._server || "unknown server"}</small>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
