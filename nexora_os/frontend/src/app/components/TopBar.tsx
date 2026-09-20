import React, { useState } from "react";
import {
  Brain,
  Search,
  Bell,
  PanelRightClose,
  PanelRightOpen,
  Cpu,
  CheckCircle2,
  AlertCircle,
  FolderGit2,
  User,
  X,
} from "lucide-react";
import { useNexora } from "../../context/NexoraContext";

export function TopBar({
  activeTab,
  rightPanelOpen,
  setRightPanelOpen,
  onOpenCommandSearch,
}: {
  activeTab: string;
  rightPanelOpen: boolean;
  setRightPanelOpen: (open: boolean) => void;
  onOpenCommandSearch: () => void;
}) {
  const { connected, status, error, events, brainState } = useNexora();
  const [showNotifications, setShowNotifications] = useState(false);

  const modelName = connected ? brainState?.active_model || "Not selected" : "Unavailable";
  const recentEvents = events.slice(-5).reverse();

  return (
    <header className="g-topbar h-14 px-4 flex items-center justify-between z-20 shrink-0 select-none">
      {/* Left: Brand & Location */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2.5">
          <div className="g-app-glyph w-8 h-8 flex items-center justify-center">
            <Brain className="w-4 h-4" />
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-semibold tracking-[0.18em] text-slate-100 font-mono flex items-center gap-1.5">
              G <span className="g-mini-badge">NEXORA</span>
            </span>
            <span className="text-[9px] text-slate-500 font-mono">LOCAL COGNITIVE OS</span>
          </div>
        </div>

        <div className="h-4 w-[1px] bg-white/10 mx-1 hidden sm:block" />

        {/* Project Selector Badge */}
        <div className="g-project-pill hidden sm:flex items-center gap-2 px-2.5 py-1 text-xs text-slate-300 font-mono">
          <FolderGit2 className="w-3.5 h-3.5 text-sky-400" />
          <span>jarvis_v3_complete</span>
        </div>
      </div>

      {/* Center: Command Search Input Trigger */}
      <button
        onClick={onOpenCommandSearch}
        className="g-command-trigger hidden md:flex items-center justify-between w-72 lg:w-96 px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 transition-all font-mono group"
      >
        <div className="flex items-center gap-2">
          <Search className="w-3.5 h-3.5 text-slate-500 group-hover:text-sky-400 transition-colors" />
          <span>Search commands, docs, memory…</span>
        </div>
        <kbd className="g-kbd px-1.5 py-0.5 text-[10px] font-mono text-slate-500">
          ⌘K
        </kbd>
      </button>

      {/* Right: Status, Model, Notifications, Panel Toggle, User Profile */}
      <div className="flex items-center gap-2 md:gap-3">
        {/* Model Badge */}
        <div className="g-model-pill hidden lg:flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono text-slate-300">
          <Cpu className="w-3 h-3 text-sky-400" />
          <span className="text-slate-400">Model:</span>
          <span className="text-sky-200 font-medium">{modelName}</span>
        </div>

        {/* Backend Connection Indicator */}
        <div className="g-status-pill flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-emerald-400 animate-pulse" : "bg-rose-500"}`} />
          <span className={connected ? "text-emerald-400 font-medium" : "text-rose-400"}>
            {connected ? "ONLINE" : "OFFLINE"}
          </span>
        </div>

        {/* Notifications Dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="g-icon-button relative"
            title="System Events"
          >
            <Bell className="w-4 h-4" />
            {events.length > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-sky-400" />
            )}
          </button>

          {showNotifications && (
            <div className="g-popover absolute right-0 mt-2 w-80 p-3 z-50 text-xs font-mono">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/10 text-slate-300 font-semibold">
                <span>System Notification Log</span>
                <button onClick={() => setShowNotifications(false)} className="text-slate-500 hover:text-slate-300">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="space-y-1.5 max-h-60 overflow-y-auto">
                {recentEvents.map((ev, idx) => (
                  <div key={idx} className="g-event-row p-1.5 text-[11px]">
                    <div className="text-sky-300 font-medium truncate">{ev.topic}</div>
                    <div className="text-slate-500 text-[10px] truncate">
                      {JSON.stringify(ev.payload)}
                    </div>
                  </div>
                ))}
                {recentEvents.length === 0 && (
                  <div className="text-slate-600 text-center py-4">No recent events</div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right Context Panel Toggle */}
        <button
          onClick={() => setRightPanelOpen(!rightPanelOpen)}
          className={`g-icon-button ${
            rightPanelOpen ? "is-active" : ""
          }`}
          title={rightPanelOpen ? "Collapse Context Panel" : "Expand Context Panel"}
        >
          {rightPanelOpen ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
        </button>

        {/* User Profile Avatar */}
        <div className="g-user-chip w-7 h-7 flex items-center justify-center text-white font-mono text-xs font-semibold">
          DEV
        </div>
      </div>
    </header>
  );
}
