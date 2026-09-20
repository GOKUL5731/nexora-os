import React, { useMemo } from "react";
import { Activity, Cpu, Zap, Database, Terminal, Shield, Layers, HardDrive, Clock } from "lucide-react";
import { cn } from "../utils";
import { useNexora } from "../../context/NexoraContext";

function MetricBar({
  label,
  value,
  colorClass = "bg-cyan-500",
}: {
  label: string;
  value: number;
  colorClass?: string;
}) {
  const v = Math.min(100, Math.max(0, value));
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[11px] font-mono">
        <span className="text-slate-400">{label}</span>
        <span className="text-slate-200 font-medium">{v.toFixed(0)}%</span>
      </div>
      <div className="h-1.5 w-full bg-slate-900/50 rounded-full overflow-hidden border border-cyan-500/10">
        <div
          className={cn("h-full rounded-full transition-all duration-300 backdrop-blur-sm", colorClass)}
          style={{ width: `${v}%` }}
        />
      </div>
    </div>
  );
}

function ModuleRow({ name, active, statusText }: { name: string; active: boolean; statusText: string }) {
  const isFailed = statusText === "FAILED" || statusText === "ERROR";
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-cyan-500/10 text-xs font-mono">
      <span className="text-slate-300 text-[11px] truncate max-w-[170px]">{name}</span>
      <div className="flex items-center gap-1.5">
        <span
          className={cn(
            "text-[9px] px-1.5 py-0.5 rounded font-mono uppercase tracking-wider border backdrop-blur-sm",
            isFailed
              ? "bg-rose-500/10 border-rose-500/20 text-rose-400"
              : active
              ? "bg-cyan-500/10 border-cyan-500/20 text-cyan-400"
              : "bg-slate-900/50 border-slate-800/50 text-slate-500"
          )}
        >
          {statusText}
        </span>
      </div>
    </div>
  );
}

const MODULE_LABELS: Record<string, string> = {
  orchestrator: "Orchestrator",
  memory_brain: "Memory Engine",
  voice_engine: "Voice Engine",
  workflow_engine: "Workflow Engine",
  visual_workflow_engine: "Graph Engine",
  nlp_pipeline: "NLP Pipeline",
  ai_lab: "AI Lab Sandbox",
  websocket_manager: "WebSocket Manager",
  cognitive_intelligence: "Cognitive Engine",
};

export function RightPanel({ open }: { open?: boolean }) {
  const { status, connected, modules: apiModules, brainState, cognitionState, agentSteps, busy } = useNexora();

  const cpu = status?.cpu ?? 0;
  const ram = status?.ram ?? 0;
  const gpu = status?.gpu?.utilization ?? 0;
  const eventsPerSec = status?.events_per_sec ?? 0;

  const modules = useMemo(() => {
    const rows: { name: string; active: boolean; statusText: string }[] = [];
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
      const keys = ["orchestrator", "memory_brain", "voice_engine", "workflow_engine", "websocket_manager", "cognitive_intelligence"];
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

  if (open === false) return null;

  return (
    <aside className="w-80 h-full bg-[#050811]/60 backdrop-blur-xl border-l border-cyan-500/10 p-4 overflow-y-auto no-scrollbar flex flex-col gap-4 shrink-0 z-10 select-none">
      {/* 1. Context Summary Header */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-[10px] font-mono text-cyan-500/60 uppercase tracking-[0.2em] border-b border-cyan-500/10 pb-2">
          <span className="flex items-center gap-1.5 text-cyan-400 font-semibold">
            <Activity className="w-3.5 h-3.5" />
            Context
          </span>
          <span className="text-[9px] text-cyan-500/40">LIVE</span>
        </div>

        {/* Current Active Model Card */}
        <div className="p-3 rounded-lg bg-cyan-500/5 border border-cyan-500/10 backdrop-blur-sm space-y-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-slate-400 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" /> Model
            </span>
            <span className="text-cyan-300 font-medium">llama3.2:1b</span>
          </div>
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
            <span>Autonomy Level:</span>
            <span className="text-slate-300">Level 4 (Full Orchestration)</span>
          </div>
        </div>
      </div>

      {/* 2. Active Task & Execution Timeline */}
      <div className="space-y-3">
        <div className="text-[10px] font-mono text-cyan-500/60 uppercase tracking-[0.2em] flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-cyan-400" /> Active Task
          </span>
          {busy && <span className="text-[9px] text-amber-400 animate-pulse">EXECUTING</span>}
        </div>
        <div className="p-3 rounded-lg bg-cyan-500/5 border border-cyan-500/10 backdrop-blur-sm text-xs font-mono space-y-2">
          <div className="text-slate-300 font-medium truncate">
            {brainState?.current_goal || (busy ? "Processing request…" : "Idle — Awaiting task")}
          </div>

          {agentSteps.length > 0 && (
            <div className="space-y-1.5 border-t border-cyan-500/10 pt-2">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Execution Timeline</span>
              {agentSteps.slice(-3).map((s) => (
                <div key={s.step} className="flex items-center gap-2 text-[11px] text-slate-400">
                  <span className="text-cyan-400 font-semibold">#{s.step}</span>
                  <span className="text-amber-300">{s.action}</span>
                  <span className="text-slate-500 truncate">{s.thought}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 3. System Performance Metrics */}
      <div className="space-y-3">
        <div className="text-[10px] font-mono text-cyan-500/60 uppercase tracking-[0.2em] flex items-center gap-1.5">
          <HardDrive className="w-3.5 h-3.5 text-cyan-400" /> System Metrics
        </div>
        <div className="p-3 rounded-lg bg-cyan-500/5 border border-cyan-500/10 backdrop-blur-sm space-y-3">
          <MetricBar label="CPU Core" value={cpu} colorClass="bg-cyan-400" />
          <MetricBar label="RAM Memory" value={ram} colorClass="bg-blue-400" />
          <MetricBar label="GPU Utilization" value={gpu} colorClass="bg-indigo-400" />

          <div className="pt-2 border-t border-cyan-500/10 grid grid-cols-2 gap-2 text-[10px] font-mono text-slate-400">
            <div>
              <span className="block text-slate-500">Events/sec</span>
              <span className="text-slate-200 font-medium">{eventsPerSec.toFixed(1)}</span>
            </div>
            <div>
              <span className="block text-slate-500">Knowledge Hits</span>
              <span className="text-slate-200 font-medium">
                {cognitionState?.last_context_summary?.knowledge_hits ?? 0}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Active System Modules */}
      <div className="space-y-3 flex-1">
        <div className="text-[10px] font-mono text-cyan-500/60 uppercase tracking-[0.2em] flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-cyan-400" /> Core Modules
        </div>
        <div className="p-3 rounded-lg bg-cyan-500/5 border border-cyan-500/10 backdrop-blur-sm space-y-1">
          {modules.map((m) => (
            <ModuleRow key={m.name} name={m.name} active={m.active} statusText={m.statusText} />
          ))}
        </div>
      </div>
    </aside>
  );
}
