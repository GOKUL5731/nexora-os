import React, { useState } from "react";
import {
  LayoutDashboard,
  MessageSquare,
  Brain,
  FolderGit2,
  BookOpen,
  Database,
  Cpu,
  Workflow,
  Settings2,
  Eye,
  Mic,
  Globe,
  FlaskConical,
  Settings,
  ChevronLeft,
  ChevronRight,
  Smartphone,
  Bot,
} from "lucide-react";
import { cn } from "../utils";

export const NAV_ITEMS = [
  { id: "dashboard", label: "Command Deck", icon: LayoutDashboard },
  { id: "chat", label: "Chat Workspace", icon: MessageSquare },
  { id: "brain", label: "Brain Core", icon: Brain },
  { id: "projects", label: "Projects", icon: FolderGit2 },
  { id: "knowledge", label: "Knowledge", icon: BookOpen },
  { id: "memory", label: "Memory DB", icon: Database },
  { id: "agents", label: "Agents Matrix", icon: Cpu },
  { id: "workflows", label: "Workflows", icon: Workflow },
  { id: "automation", label: "Automation", icon: Settings2 },
  { id: "vision", label: "Vision AI", icon: Eye },
  { id: "voice", label: "Voice AI", icon: Mic },
  { id: "connectors", label: "Connectors", icon: Globe },
  { id: "companion", label: "Companion", icon: Smartphone },
  { id: "pet-g", label: "Pet G", icon: Bot },
  { id: "lab", label: "AI LAB", icon: FlaskConical },
  { id: "settings", label: "Settings", icon: Settings },
];

export function Sidebar({
  activeTab,
  setActiveTab,
  collapsed,
  setCollapsed,
}: {
  activeTab: string;
  setActiveTab: (id: string) => void;
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
}) {
  return (
    <aside
      className={cn(
        "g-sidebar h-full flex flex-col justify-between transition-all duration-300 z-20 shrink-0 select-none",
        collapsed ? "w-16" : "w-56"
      )}
    >
      {/* Top Header / Collapse Toggle */}
      <div className="g-sidebar-brand p-3 flex items-center justify-between">
        {!collapsed && (
          <span className="g-brand-mark px-2">G OPERATING DECK</span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="g-icon-button mx-auto"
          title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation List */}
      <div className="flex-1 py-2 overflow-y-auto no-scrollbar space-y-1 px-2">
        {NAV_ITEMS.map((item) => {
          const isActive = activeTab === item.id;
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              aria-label={item.label}
              aria-current={isActive ? "page" : undefined}
              onClick={() => setActiveTab(item.id)}
              className={cn(
                "g-nav-item w-full flex items-center gap-3 px-3 py-2.5 text-xs font-mono transition-all duration-300 relative group",
                isActive
                  ? "is-active text-slate-50 font-medium"
                  : "text-slate-500 hover:text-slate-200"
              )}
            >
              <Icon
                className={cn(
                  "w-4 h-4 shrink-0 transition-all duration-300",
                  isActive ? "text-sky-300" : "text-slate-600 group-hover:text-sky-400"
                )}
              />
              {!collapsed && <span className="truncate tracking-wide">{item.label}</span>}

              {/* Tooltip in Collapsed Mode */}
              {collapsed && (
                <div className="g-nav-tooltip absolute left-14 px-2.5 py-1 text-xs opacity-0 group-hover:opacity-100 pointer-events-none transition-all duration-300 whitespace-nowrap z-50 font-mono">
                  {item.label}
                </div>
              )}
            </button>
          );
        })}
      </div>

    </aside>
  );
}
