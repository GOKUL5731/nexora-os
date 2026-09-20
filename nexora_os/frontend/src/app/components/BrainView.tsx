import React from "react";
import { motion, AnimatePresence } from "motion/react";
import { Activity, Brain, CheckCircle, Cpu, Database, Loader2, Network, XCircle, Zap } from "lucide-react";
import { useNexora } from "../../context/NexoraContext";

const NODE_META = [
  { key: "cpu", label: "CPU", icon: Cpu },
  { key: "memory", label: "Memory", icon: Database },
  { key: "events", label: "Event Bus", icon: Activity },
  { key: "agents", label: "Agents", icon: Zap },
  { key: "workflows", label: "Workflows", icon: Network },
  { key: "modules", label: "Modules", icon: Brain },
];

// Cognitive loop stages in order
const DEFAULT_COGNITIVE_STAGES = [
  "PERCEIVE", "UNDERSTAND", "REMEMBER", "PLAN", "SELECT",
  "EXECUTE", "OBSERVE", "VERIFY", "REFLECT", "LEARN",
];

const STAGE_COLORS: Record<string, string> = {
  PERCEIVE:          "border-blue-500/50 text-blue-400 bg-blue-950/20",
  UNDERSTAND:        "border-purple-500/50 text-purple-400 bg-purple-950/20",
  RETRIEVE_MEMORY:   "border-indigo-500/50 text-indigo-400 bg-indigo-950/20",
  REMEMBER:          "border-indigo-500/50 text-indigo-400 bg-indigo-950/20",
  FORM_GOAL:         "border-cyan-500/50 text-cyan-400 bg-cyan-950/20",
  PLAN:              "border-cyan-500/50 text-cyan-400 bg-cyan-950/20",
  SELECT_CAPABILITY: "border-teal-500/50 text-teal-400 bg-teal-950/20",
  SELECT:            "border-teal-500/50 text-teal-400 bg-teal-950/20",
  EXECUTE:           "border-yellow-500/50 text-yellow-400 bg-yellow-950/20",
  OBSERVE_RESULT:    "border-orange-500/50 text-orange-400 bg-orange-950/20",
  OBSERVE:           "border-orange-500/50 text-orange-400 bg-orange-950/20",
  VERIFY:            "border-green-500/50 text-green-400 bg-green-950/20",
  REFLECT:           "border-emerald-500/50 text-emerald-400 bg-emerald-950/20",
  LEARN:             "border-lime-500/50 text-lime-400 bg-lime-950/20",
  COMPLETE:          "border-emerald-600/60 text-emerald-300 bg-emerald-950/30",
  FAILED:            "border-red-500/50 text-red-400 bg-red-950/20",
  IDLE:              "border-cyan-800/30 text-cyan-700 bg-black/20",
};

export function BrainView() {
  const { status, agents, workflows, modules, memoryCount, events, brainState, cognitionState } = useNexora();
  const values: Record<string, string> = {
    cpu: `${status?.cpu?.toFixed(0) ?? 0}%`,
    memory: `${memoryCount} chunks`,
    events: `${status?.events_per_sec?.toFixed(1) ?? 0}/s`,
    agents: `${agents.runtime.filter((a) => a.status === "running").length} active`,
    workflows: `${workflows.length} stored`,
    modules: `${modules.filter((m) => ["online", "running"].includes(m.status)).length} online`,
  };

  const currentStage = brainState?.stage ?? "IDLE";
  const cognitiveStages = cognitionState?.loop?.length ? cognitionState.loop : DEFAULT_COGNITIVE_STAGES;
  const currentStageIdx = cognitiveStages.indexOf(currentStage);
  const plan = brainState?.current_plan as Array<{ id: string; action: string; status: string }> | undefined;
  const isActive = currentStage !== "IDLE" && currentStage !== "COMPLETE" && currentStage !== "FAILED";
  const monitor = cognitionState?.last_monitor ?? {};
  const contextSummary = cognitionState?.last_context_summary ?? {};

  return (
    <div className="w-full h-full relative overflow-auto p-8 pointer-events-none">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,255,255,0.06)_0%,transparent_70%)] pointer-events-none" />
      <div className="relative max-w-5xl mx-auto min-h-full flex flex-col justify-center gap-8 pointer-events-auto">
        {/* Header */}
        <div>
          <h2 className="font-['Rajdhani'] text-2xl tracking-[0.2em] uppercase text-cyan-300 flex items-center gap-3">
            <Brain className="w-6 h-6" />
            Cognitive Network
            {isActive && <Loader2 className="w-4 h-4 animate-spin text-cyan-500 ml-2" />}
          </h2>
          <p className="text-xs font-mono text-cyan-700 mt-2">Live runtime state — cognitive loop, goal tracking, and event bus.</p>
        </div>

        {/* Persistent Cognitive Identity */}
        <div className="border border-cyan-500/25 bg-black/50 rounded-xl p-5">
          <p className="text-[10px] font-mono text-cyan-700 uppercase mb-3">Cognitive Identity</p>
          <div className="grid md:grid-cols-4 gap-3 text-xs font-mono">
            <div>
              <span className="block text-cyan-700 uppercase text-[10px]">Assistant</span>
              <span className="text-cyan-100">{cognitionState?.identity?.name ?? "Jarvis"}</span>
            </div>
            <div>
              <span className="block text-cyan-700 uppercase text-[10px]">Role</span>
              <span className="text-cyan-100">{cognitionState?.identity?.role ?? "adaptive assistant"}</span>
            </div>
            <div>
              <span className="block text-cyan-700 uppercase text-[10px]">Knowledge</span>
              <span className="text-cyan-100">{cognitionState?.knowledge?.domains ?? 0} domains / {cognitionState?.knowledge?.entries ?? 0} entries</span>
            </div>
            <div>
              <span className="block text-cyan-700 uppercase text-[10px]">Memory</span>
              <span className="text-cyan-100">{cognitionState?.memory_count ?? memoryCount} chunks</span>
            </div>
          </div>
          <div className="mt-4 grid md:grid-cols-3 gap-2 text-[11px] font-mono text-cyan-600">
            <span>Completed: {String(monitor.completed ?? false)}</span>
            <span>Verified: {String(monitor.verification_succeeded ?? false)}</span>
            <span>Remember: {String(monitor.should_remember ?? false)}</span>
          </div>
          <div className="mt-2 text-[11px] font-mono text-cyan-700 truncate">
            Context: {contextSummary.memory_hits ?? 0} memories, {contextSummary.knowledge_hits ?? 0} knowledge hits, {contextSummary.perceived_inputs ?? 0} perceived inputs
          </div>
        </div>

        {/* Central Brain Status */}
        <div className="border border-cyan-500/25 bg-black/50 rounded-xl p-5">
          <p className="text-[10px] font-mono text-cyan-700 uppercase mb-3">Central Brain State</p>
          <div className="grid md:grid-cols-4 gap-3 text-xs font-mono">
            <div>
              <span className="block text-cyan-700 uppercase text-[10px]">Stage</span>
              <span className={`inline-block mt-0.5 px-2 py-0.5 rounded text-[10px] border font-bold ${STAGE_COLORS[currentStage] ?? STAGE_COLORS.IDLE}`}>
                {currentStage}
              </span>
            </div>
            <div>
              <span className="block text-cyan-700 uppercase text-[10px]">Capability</span>
              <span className="text-cyan-100">{brainState?.selected_capability || "none"}</span>
            </div>
            <div>
              <span className="block text-cyan-700 uppercase text-[10px]">Verification</span>
              <span className="text-cyan-100 flex items-center gap-1">
                {brainState?.verification_status === "SUCCESS" && <CheckCircle className="w-3 h-3 text-emerald-400" />}
                {brainState?.verification_status === "FAILED" && <XCircle className="w-3 h-3 text-red-400" />}
                {brainState?.verification_status ?? "UNKNOWN"}
              </span>
            </div>
            <div>
              <span className="block text-cyan-700 uppercase text-[10px]">Goals Tracked</span>
              <span className="text-cyan-100">{brainState?.goals?.length ?? 0}</span>
            </div>
          </div>
          <div className="mt-4 text-xs font-mono text-cyan-500 truncate">
            Goal: {brainState?.current_goal || "none"}
          </div>
        </div>

        {/* Cognitive Loop Pipeline */}
        <div className="border border-cyan-900/40 bg-black/40 rounded-xl p-5">
          <p className="text-[10px] font-mono text-cyan-700 uppercase mb-4">Cognitive Loop</p>
          <div className="flex flex-wrap gap-2">
            {cognitiveStages.map((stage, idx) => {
              const isCurrentStage = stage === currentStage;
              const isPast = currentStageIdx > idx && currentStageIdx !== -1;
              const color = isCurrentStage
                ? STAGE_COLORS[stage]
                : isPast
                  ? "border-emerald-800/30 text-emerald-700 bg-emerald-950/10"
                  : "border-cyan-900/30 text-cyan-800 bg-black/20";
              return (
                <motion.div
                  key={stage}
                  animate={isCurrentStage ? { scale: [1, 1.06, 1] } : { scale: 1 }}
                  transition={{ repeat: isCurrentStage ? Infinity : 0, duration: 1.4 }}
                  className={`px-2.5 py-1 rounded border text-[10px] font-mono uppercase tracking-wider flex items-center gap-1 ${color}`}
                >
                  {isCurrentStage && <Loader2 className="w-2.5 h-2.5 animate-spin" />}
                  {isPast && !isCurrentStage && <CheckCircle className="w-2.5 h-2.5" />}
                  {stage}
                </motion.div>
              );
            })}
          </div>
        </div>

        {/* Live Plan Steps */}
        <AnimatePresence>
          {plan && plan.length > 0 && (
            <motion.div
              key="plan"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="border border-cyan-900/40 bg-black/40 rounded-xl p-5"
            >
              <p className="text-[10px] font-mono text-cyan-700 uppercase mb-3">Execution Plan Steps</p>
              <div className="space-y-2">
                {plan.map((step) => (
                  <div key={step.id} className="flex items-center gap-3 text-xs font-mono">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${
                      step.status === "completed" ? "text-emerald-400 border-emerald-800/40" :
                      step.status === "failed" ? "text-red-400 border-red-800/40" :
                      "text-cyan-600 border-cyan-900/40"
                    }`}>
                      {step.status}
                    </span>
                    <span className="text-cyan-500 truncate">{step.action}</span>
                    <span className="text-cyan-800 ml-auto shrink-0">{step.id}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Metrics Grid */}
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

        {/* Recent Events */}
        <div className="border border-cyan-900/40 bg-black/40 rounded-xl p-4">
          <p className="text-[10px] font-mono text-cyan-600 uppercase mb-3">Recent Cognitive Events</p>
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
