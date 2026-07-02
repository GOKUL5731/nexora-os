import React, { useMemo } from "react";
import { Activity, Zap } from "lucide-react";
import { cn } from "../utils";
import { useNexora } from "../../context/NexoraContext";

function MetricBar({
  label,
  value,
  colorClass = "bg-cyan-500",
  glowClass = "shadow-[0_0_10px_rgba(0,255,255,0.5)]",
}: {
  label: string;
  value: number;
  colorClass?: string;
  glowClass?: string;
}) {
  const v = Math.min(100, Math.max(0, value));
  return (
    <div className="mb-5">
      <div className="flex justify-between text-xs font-['Rajdhani'] tracking-[0.1em] mb-1.5">
        <span className="text-cyan-500/80 uppercase font-semibold">{label}</span>
        <span className="text-cyan-300 font-mono">{v.toFixed(0)}%</span>
      </div>
      <div className="h-1.5 w-full bg-black/60 rounded-full overflow-hidden border border-cyan-900/30">
        <div
          className={cn("h-full rounded-full transition-all duration-500", colorClass, glowClass)}
          style={{ width: `${v}%` }}
        />
      </div>
    </div>
  );
}

function ModuleStatus({ name, active, statusText }: { name: string; active: boolean; statusText: string }) {
  const isFailed = statusText === "FAILED" || statusText === "ERROR";
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-cyan-900/20 group hover:bg-cyan-950/20 px-2 -mx-2 rounded transition-colors">
      <span className="text-[13px] font-['Rajdhani'] tracking-wider text-cyan-200 group-hover:text-white transition-colors">
        {name}
      </span>
      <div className="flex items-center gap-2">
        <span className={cn(
          "text-[9px] font-mono tracking-widest",
          isFailed ? "text-red-400 font-semibold" : "text-cyan-600/80"
        )}>
          {statusText}
        </span>
        <div
          className={cn(
            "w-1.5 h-1.5 rounded-full",
            isFailed
              ? "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)] animate-[pulse_1s_ease-in-out_infinite]"
              : active
                ? "bg-cyan-400 shadow-[0_0_8px_rgba(0,255,255,0.8)] animate-[pulse_2s_ease-in-out_infinite]"
                : "bg-cyan-900",
          )}
        />
      </div>
    </div>
  );
}

const MODULE_LABELS: Record<string, string> = {
  orchestrator: "Orchestrator",
  memory_brain: "Memory Brain",
  voice_engine: "Voice Engine",
  workflow_engine: "Workflow Engine",
  visual_workflow_engine: "Graph Engine",
  nlp_pipeline: "NLP Pipeline",
  ai_lab: "AI Lab Sandbox",
  websocket_manager: "WebSocket Bridge",
};

export function RightPanel() {
  const { status, connected, modules: apiModules } = useNexora();
  const cpu = status?.cpu ?? 0;
  const ram = status?.ram ?? 0;
  const gpu = status?.gpu?.utilization ?? 0;

  const modules = useMemo(() => {
    const rows: { name: string; active: boolean; statusText: string }[] = [];
    const keys = ["orchestrator", "memory_brain", "voice_engine", "workflow_engine", "visual_workflow_engine", "nlp_pipeline", "ai_lab", "websocket_manager"];
    
    if (apiModules && apiModules.length > 0) {
      apiModules.forEach((m) => {
        const isOnline = m.status === "online" || m.status === "running";
        rows.push({
          name: MODULE_LABELS[m.name] ?? m.name,
          active: connected && isOnline,
          statusText: m.status.toUpperCase(),
        });
      });
    } else {
      for (const key of keys) {
        rows.push({
          name: MODULE_LABELS[key] ?? key,
          active: false,
          statusText: "STANDBY",
        });
      }
    }
    return rows;
  }, [apiModules, connected]);

  return (
    <div className="w-[340px] h-full bg-black/60 backdrop-blur-xl border-l border-cyan-500/20 p-6 overflow-y-auto no-scrollbar hidden lg:flex flex-col z-10 shadow-[-20px_0_40px_rgba(0,0,0,0.5)]">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-6 text-cyan-400 border-b border-cyan-900/30 pb-2">
          <Activity className="w-5 h-5" />
          <h2 className="text-sm font-['Rajdhani'] font-bold tracking-[0.2em] uppercase">System Overview</h2>
        </div>

        <div className="p-5 rounded-xl border border-cyan-500/20 bg-gradient-to-b from-cyan-950/20 to-black/40 mb-6 relative overflow-hidden shadow-[inset_0_0_20px_rgba(0,255,255,0.05)]">
          <MetricBar label="CPU CORE" value={cpu} />
          <MetricBar label="GPU UTIL" value={gpu} colorClass="bg-blue-400" glowClass="shadow-[0_0_12px_rgba(59,130,246,0.6)]" />
          <MetricBar label="MEMORY" value={ram} />
          <div className="mt-4 pt-4 border-t border-cyan-900/30 text-[10px] font-mono text-cyan-600 flex justify-between">
            <span>LLM</span>
            <span className={status?.llm_ready ? "text-green-400" : "text-amber-500"}>
              {status?.llm_ready ? "ONLINE" : "OFFLINE"}
            </span>
          </div>
          <div className="text-[10px] font-mono text-cyan-600 flex justify-between mt-1">
            <span>Events/s</span>
            <span>{status?.events_per_sec?.toFixed(1) ?? "—"}</span>
          </div>
        </div>
      </div>

      <div className="flex-1">
        <div className="flex items-center gap-3 mb-6 text-cyan-400 border-b border-cyan-900/30 pb-2">
          <Zap className="w-5 h-5" />
          <h2 className="text-sm font-['Rajdhani'] font-bold tracking-[0.2em] uppercase">Active Modules</h2>
        </div>
        <div className="flex flex-col bg-black/40 border border-cyan-500/20 rounded-xl p-4 shadow-[inset_0_0_20px_rgba(0,255,255,0.05)]">
          {modules.map((m) => (
            <ModuleStatus key={m.name} name={m.name} active={m.active} statusText={m.statusText} />
          ))}
        </div>
      </div>
    </div>
  );
}
