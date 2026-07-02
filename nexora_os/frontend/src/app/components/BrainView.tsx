import React from "react";
import { motion } from "motion/react";
import { Activity, Brain, Cpu, Database, Network, Zap } from "lucide-react";
import { useNexora } from "../../context/NexoraContext";

const NODE_META = [
  { key: "cpu", label: "CPU", icon: Cpu },
  { key: "memory", label: "Memory", icon: Database },
  { key: "events", label: "Event Bus", icon: Activity },
  { key: "agents", label: "Agents", icon: Zap },
  { key: "workflows", label: "Workflows", icon: Network },
  { key: "modules", label: "Modules", icon: Brain },
];

export function BrainView() {
  const { status, agents, workflows, modules, memoryCount, events } = useNexora();
  const values: Record<string, string> = {
    cpu: `${status?.cpu?.toFixed(0) ?? 0}%`,
    memory: `${memoryCount} chunks`,
    events: `${status?.events_per_sec?.toFixed(1) ?? 0}/s`,
    agents: `${agents.runtime.filter((agent) => agent.status === "running").length} active`,
    workflows: `${workflows.length} stored`,
    modules: `${modules.filter((module) => ["online", "running"].includes(module.status)).length} online`,
  };

  return (
    <div className="w-full h-full relative overflow-auto p-8">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,255,255,0.06)_0%,transparent_70%)] pointer-events-none" />
      <div className="relative max-w-5xl mx-auto min-h-full flex flex-col justify-center gap-8">
        <div>
          <h2 className="font-['Rajdhani'] text-2xl tracking-[0.2em] uppercase text-cyan-300 flex items-center gap-3">
            <Brain className="w-6 h-6" /> Cognitive Network
          </h2>
          <p className="text-xs font-mono text-cyan-700 mt-2">Live runtime state from memory, agents, workflows and the event bus.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {NODE_META.map(({ key, label, icon: Icon }, index) => (
            <motion.div
              key={key}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.06 }}
              className="border border-cyan-500/25 bg-black/50 rounded-xl p-5"
            >
              <div className="flex items-center justify-between">
                <Icon className="w-5 h-5 text-cyan-500" />
                <span className="text-[10px] font-mono text-cyan-700 uppercase">{label}</span>
              </div>
              <p className="mt-5 text-2xl font-['Rajdhani'] text-cyan-100">{values[key]}</p>
            </motion.div>
          ))}
        </div>
        <div className="border border-cyan-900/40 bg-black/40 rounded-xl p-4">
          <p className="text-[10px] font-mono text-cyan-600 uppercase mb-3">Recent cognitive events</p>
          <div className="grid md:grid-cols-2 gap-2">
            {events.slice(-8).reverse().map((event) => (
              <div key={event.sequence} className="text-[11px] font-mono text-cyan-500 truncate">
                {event.sequence} · {event.topic}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
