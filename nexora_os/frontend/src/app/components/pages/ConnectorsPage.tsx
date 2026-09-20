import React, { useCallback, useEffect, useState } from "react";
import { motion } from "motion/react";
import { Globe, HardDrive, Monitor, Terminal, Wifi, WifiOff, Play, RefreshCw, Smartphone, Code } from "lucide-react";
import { nexoraApi } from "../../../api/client";

type ConnectorInfo = {
  name: string;
  health: string;
  capabilities: string[];
};

const CONNECTOR_ICONS: Record<string, React.ElementType> = {
  desktop: Monitor,
  browser: Globe,
  terminal: Terminal,
  filesystem: HardDrive,
  android: Smartphone,
  vscode: Code,
};

const HEALTH_COLORS: Record<string, string> = {
  AVAILABLE: "text-emerald-400 border-emerald-500/30 bg-emerald-950/20",
  DEGRADED: "text-yellow-400 border-yellow-500/30 bg-yellow-950/20",
  UNAVAILABLE: "text-red-400 border-red-500/30 bg-red-950/20",
  FAILED: "text-red-500 border-red-600/30 bg-red-950/30",
  UNCONFIGURED: "text-cyan-700 border-cyan-800/30 bg-cyan-950/10",
};

export function ConnectorsPage() {
  const [connectors, setConnectors] = useState<ConnectorInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [execResult, setExecResult] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await nexoraApi.connectors();
      setConnectors(data.connectors ?? []);
    } catch {
      setConnectors([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runAction = async (connectorName: string, action: string) => {
    try {
      const result = await nexoraApi.connectorExecute(connectorName, action);
      setExecResult((prev) => ({
        ...prev,
        [connectorName]: JSON.stringify(result, null, 2),
      }));
    } catch (e) {
      setExecResult((prev) => ({
        ...prev,
        [connectorName]: `Error: ${e instanceof Error ? e.message : String(e)}`,
      }));
    }
  };

  return (
    <div className="flex-1 p-8 overflow-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-['Rajdhani'] text-cyan-400 tracking-widest uppercase">
          Connectors
        </h2>
        <button
          onClick={refresh}
          disabled={loading}
          className="flex items-center gap-2 text-xs font-mono text-cyan-500 hover:text-cyan-300 disabled:opacity-40 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {connectors.length === 0 && !loading && (
        <div className="text-center py-20 text-cyan-700 font-mono text-sm">
          No connectors registered. Backend may still be initializing.
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        {connectors.map((conn, index) => {
          const Icon = CONNECTOR_ICONS[conn.name] ?? Wifi;
          const colorClass = HEALTH_COLORS[conn.health] ?? "text-cyan-500 border-cyan-500/20 bg-cyan-950/10";
          const isAvailable = conn.health === "AVAILABLE" || conn.health === "DEGRADED";

          return (
            <motion.div
              key={conn.name}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.07 }}
              className={`rounded-xl border p-5 ${colorClass}`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2.5">
                  <Icon className="w-5 h-5" />
                  <span className="font-['Rajdhani'] text-lg capitalize">{conn.name}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {isAvailable ? (
                    <Wifi className="w-3.5 h-3.5" />
                  ) : (
                    <WifiOff className="w-3.5 h-3.5" />
                  )}
                  <span className="text-[10px] font-mono uppercase tracking-wider">{conn.health}</span>
                </div>
              </div>

              <div className="flex flex-wrap gap-1.5 mb-4">
                {conn.capabilities.map((cap) => (
                  <span
                    key={cap}
                    className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-current/20 opacity-70"
                  >
                    {cap}
                  </span>
                ))}
              </div>

              {/* Quick action buttons for common capabilities */}
              <div className="flex flex-wrap gap-2">
                {conn.capabilities.slice(0, 3).map((cap) => (
                  <button
                    key={cap}
                    onClick={() => runAction(conn.name, cap)}
                    disabled={!isAvailable}
                    className="flex items-center gap-1 text-[10px] font-mono px-2.5 py-1 rounded border border-current/30 hover:bg-current/10 disabled:opacity-30 transition-colors"
                  >
                    <Play className="w-2.5 h-2.5" />
                    {cap}
                  </button>
                ))}
              </div>

              {execResult[conn.name] && (
                <pre className="mt-3 max-h-32 overflow-auto p-3 rounded border border-current/20 bg-black/40 text-[9px] font-mono opacity-80 whitespace-pre-wrap">
                  {execResult[conn.name]}
                </pre>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
