import React, { useState } from "react";
import { Mic, Cpu, Network, Database, Brain, Languages, Send } from "lucide-react";
import { cn } from "../utils";
import { useNexora } from "../../context/NexoraContext";
import { motion, AnimatePresence } from "motion/react";

const TOOL_ICONS: Record<string, string> = {
  run_command: "⚡",
  read_file: "📄",
  write_file: "✏️",
  launch_app: "🚀",
  open_url: "🌐",
  search_web: "🔍",
  ask_user: "❓",
  complete: "✅",
};

function GlassPanel({ title, icon: Icon, children, className }: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "bg-black/50 backdrop-blur-xl border border-cyan-500/20 rounded-xl p-4 flex flex-col relative overflow-hidden group hover:border-cyan-400/40 transition-colors shadow-[0_8px_32px_rgba(0,0,0,0.4)]",
        className,
      )}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-cyan-400/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
      <div className="flex items-center gap-3 mb-4 text-cyan-400 border-b border-cyan-900/30 pb-2">
        <Icon className="w-4 h-4 drop-shadow-[0_0_8px_rgba(0,255,255,0.8)]" />
        <h3 className="text-xs font-['Rajdhani'] font-bold tracking-[0.2em] uppercase text-cyan-50">{title}</h3>
      </div>
      <div className="flex-1 relative z-10">{children}</div>
    </div>
  );
}

export function LowerPanels() {
  const { voiceState, lastMessage, agents, workflows, memoryItems, memoryCount, status, agentSteps, pendingQuestion, busy, sendCommand } = useNexora();
  const [questionReply, setQuestionReply] = useState("");

  const handleAnswerQuestion = async () => {
    if (!questionReply.trim()) return;
    await sendCommand(questionReply);
    setQuestionReply("");
  };

  return (
    <div className="w-full h-[40%] min-h-[300px] p-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4 z-10 overflow-y-auto no-scrollbar pb-10">
      <GlassPanel title="Voice Stream" icon={Mic} className="col-span-1">
        <div className="flex flex-col h-full justify-between text-xs font-['Rajdhani'] text-cyan-400">
          <div className="flex justify-between mb-2">
            <span>MIC: {voiceState === "listening" ? "LISTENING" : voiceState.toUpperCase()}</span>
            <Languages className="w-3 h-3" />
          </div>
          <p className="text-[11px] text-cyan-300/80 font-mono italic flex-1 py-2">"{lastMessage.slice(0, 120)}"</p>
          <span className="text-[10px] text-cyan-600 font-mono">EN / TA / Tanglish</span>
        </div>
      </GlassPanel>

      {/* Autonomous Thinking Panel — replaces static Agent Swarm when busy */}
      <GlassPanel title={busy && agentSteps.length > 0 ? "Autonomous Thinking" : "Agent Swarm"} icon={busy && agentSteps.length > 0 ? Brain : Cpu} className="col-span-1 xl:col-span-2">
        <AnimatePresence mode="wait">
          {busy && agentSteps.length > 0 ? (
            <motion.div
              key="thinking"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col gap-1.5 overflow-y-auto max-h-[120px] pr-1"
            >
              {agentSteps.slice(-5).map((s) => (
                <motion.div
                  key={s.step}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-start gap-2 text-[10px] font-mono"
                >
                  <span className="text-cyan-600 shrink-0">#{s.step}</span>
                  <span className="text-yellow-400/80 shrink-0">{TOOL_ICONS[s.action] ?? "🔧"} {s.action}</span>
                  <span className="text-cyan-300/60 truncate">{s.thought}</span>
                </motion.div>
              ))}
              <div className="flex items-center gap-1 text-[10px] text-cyan-500 font-mono mt-1">
                <span className="inline-block w-1.5 h-1.5 bg-cyan-400 rounded-full animate-pulse" />
                Working…
              </div>
            </motion.div>
          ) : pendingQuestion ? (
            <motion.div key="question" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-2">
              <p className="text-[11px] text-yellow-300 font-mono">❓ {pendingQuestion}</p>
              <div className="flex gap-1">
                <input
                  value={questionReply}
                  onChange={(e) => setQuestionReply(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAnswerQuestion()}
                  className="flex-1 bg-black/50 border border-cyan-700/50 rounded px-2 py-1 text-[10px] text-cyan-100 outline-none font-mono"
                  placeholder="Your answer…"
                />
                <button onClick={handleAnswerQuestion} className="p-1 text-cyan-400 hover:text-cyan-200">
                  <Send className="w-3 h-3" />
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div key="agents" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-2">
              {agents.runtime.slice(0, 4).map((a) => (
                <div key={a.name} className="flex justify-between p-2 rounded bg-cyan-950/30 border border-cyan-900/30">
                  <span className="text-xs text-cyan-100 font-['Rajdhani']">{a.name}</span>
                  <span className="text-[9px] font-mono text-cyan-500">{a.status?.toUpperCase()}</span>
                </div>
              ))}
              {!agents.runtime.length && (
                <span className="text-[10px] text-cyan-700 font-mono">No agents active. Send a complex task to activate.</span>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </GlassPanel>

      <GlassPanel title="Workflow Trace" icon={Network} className="col-span-1">
        <div className="flex flex-col gap-1.5 text-[10px] font-mono text-cyan-600">
          {workflows.slice(0, 4).map((w) => (
            <div key={w.name} className="truncate">
              {w.enabled ? "▶" : "○"} {w.name} ({w.step_count ?? 0} steps)
            </div>
          ))}
          {!workflows.length && <span>No workflows registered</span>}
        </div>
      </GlassPanel>

      <GlassPanel title="Memory DB" icon={Database} className="col-span-1">
        <div className="text-[10px] font-mono text-cyan-600 mb-2">{memoryCount} interactions</div>
        {memoryItems.slice(0, 3).map((m, i) => (
          <div key={i} className="truncate text-[10px] text-cyan-500/80 mb-1">
            • {m.summary ?? "—"}
          </div>
        ))}
        {agentSteps.length > 0 && !busy && (
          <div className="mt-2 text-[9px] text-cyan-700 font-mono border-t border-cyan-900/30 pt-1">
            Last run: {agentSteps.length} steps completed
          </div>
        )}
      </GlassPanel>
    </div>
  );
}
