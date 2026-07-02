import React from "react";
import { 
  Home, Brain, Mic, Eye, Cpu, Network, 
  Settings2, Database, FlaskConical, Settings
} from "lucide-react";
import { cn } from "../utils";

const navItems = [
  { id: "home", label: "Home", icon: Home },
  { id: "brain", label: "Brain", icon: Brain },
  { id: "voice", label: "Voice", icon: Mic },
  { id: "vision", label: "Vision", icon: Eye },
  { id: "agents", label: "Agents", icon: Cpu },
  { id: "workflows", label: "Workflows", icon: Network },
  { id: "automation", label: "Automation", icon: Settings2 },
  { id: "memory", label: "Memory", icon: Database },
  { id: "lab", label: "AI LAB", icon: FlaskConical },
];

export function Sidebar({
  activeTab,
  setActiveTab,
  connected = false,
}: {
  activeTab: string;
  setActiveTab: (id: string) => void;
  connected?: boolean;
}) {
  return (
    <div className="flex flex-col w-[64px] md:w-[80px] h-full border-r border-cyan-900/30 bg-black/40 backdrop-blur-md py-6 justify-between relative z-10 shrink-0">
      {/* Top logo/icon */}
      <div className="flex justify-center mb-8">
        <div className="w-10 h-10 rounded-full border border-cyan-500/50 flex items-center justify-center shadow-[0_0_15px_rgba(0,255,255,0.2)]">
          <Brain className="w-5 h-5 text-cyan-400" />
        </div>
      </div>

      {/* Nav items */}
      <div className="flex-1 flex flex-col items-center gap-6 overflow-y-auto overflow-x-hidden no-scrollbar">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className="relative group flex items-center justify-center w-10 h-10 md:w-12 md:h-12 rounded-xl transition-all duration-300"
            >
              {isActive && (
                <div className="absolute inset-0 bg-cyan-500/20 rounded-xl blur-sm shadow-[0_0_20px_rgba(0,255,255,0.4)]" />
              )}
              <div className={cn(
                "relative z-10 transition-colors duration-300",
                isActive ? "text-cyan-300" : "text-cyan-800 group-hover:text-cyan-500"
              )}>
                <item.icon className="w-6 h-6" strokeWidth={isActive ? 2 : 1.5} />
              </div>
              
              {/* Tooltip */}
              <div className="hidden lg:block absolute left-16 px-2 py-1 bg-black/80 border border-cyan-900/50 text-cyan-400 text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap font-['Rajdhani'] tracking-wider">
                {item.label}
              </div>
            </button>
          );
        })}
      </div>

      {/* Bottom controls */}
      <div className="flex flex-col items-center gap-6 mt-8">
        <button
          onClick={() => setActiveTab("settings")}
          aria-label="Settings"
          className="relative group flex items-center justify-center w-10 h-10 md:w-12 md:h-12 rounded-xl transition-all duration-300"
        >
          <Settings className="w-6 h-6 text-cyan-800 group-hover:text-cyan-500 transition-colors duration-300" strokeWidth={1.5} />
        </button>

        <div className="flex flex-col items-center gap-2 mb-2">
          <div className={cn(
            "w-2 h-2 rounded-full shadow-[0_0_10px_rgba(0,255,255,0.8)]",
            connected ? "bg-cyan-500 animate-pulse" : "bg-red-500/70"
          )} />
          <span className="text-[10px] text-cyan-600 font-['Rajdhani'] font-bold tracking-widest rotate-180" style={{ writingMode: 'vertical-rl' }}>
            {connected ? "ONLINE" : "OFFLINE"}
          </span>
        </div>
      </div>
    </div>
  );
}
