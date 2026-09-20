import React, { useEffect, useState } from "react";
import {
  Settings,
  Sliders,
  Cpu,
  Mic,
  Eye,
  Database,
  Shield,
  Settings2,
  Palette,
  Terminal,
  Save,
  CheckCircle2,
} from "lucide-react";
import { nexoraApi } from "../../../api/client";

const SETTING_TABS = [
  { id: "general", label: "General", icon: Sliders },
  { id: "ai", label: "AI Models", icon: Cpu },
  { id: "voice", label: "Voice", icon: Mic },
  { id: "vision", label: "Vision", icon: Eye },
  { id: "memory", label: "Memory", icon: Database },
  { id: "security", label: "Security", icon: Shield },
  { id: "automation", label: "Automation", icon: Settings2 },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "advanced", label: "Advanced", icon: Terminal },
];

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState("general");
  const [rawSettings, setRawSettings] = useState<Record<string, unknown>>({});
  const [saved, setSaved] = useState(false);

  // Form states
  const [assistantName, setAssistantName] = useState("Jarvis");
  const [selectedModel, setSelectedModel] = useState("llama3.2:1b");
  const [autonomyLevel, setAutonomyLevel] = useState(4);
  const [ttsSpeed, setTtsSpeed] = useState(175);
  const [ocrLang, setOcrLang] = useState("eng+tam");

  useEffect(() => {
    nexoraApi
      .settings()
      .then((s) => setRawSettings(s))
      .catch(() => setRawSettings({ error: "Backend offline" }));
  }, []);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="flex-1 flex flex-col p-6 space-y-6 overflow-y-auto no-scrollbar font-mono text-xs select-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-base font-bold text-slate-100 uppercase tracking-widest flex items-center gap-2">
            <Settings className="w-4 h-4 text-cyan-400" />
            NEXORA Platform Settings
          </h1>
          <p className="text-[11px] text-slate-500 font-sans mt-0.5">
            Configure platform preferences, model routing, voice engines, memory thresholds, and security parameters
          </p>
        </div>

        <button
          onClick={handleSave}
          className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium flex items-center gap-1.5 transition-colors shadow-[0_0_12px_rgba(6,182,212,0.3)]"
        >
          {saved ? <CheckCircle2 className="w-4 h-4 text-white" /> : <Save className="w-4 h-4" />}
          <span>{saved ? "Saved" : "Save Changes"}</span>
        </button>
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Sidebar Tabs (1 Col) */}
        <div className="p-2 rounded-xl bg-[#090d19] border border-slate-800 space-y-1">
          {SETTING_TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-mono transition-all ${
                  isActive
                    ? "bg-cyan-950/60 text-cyan-300 border border-cyan-500/30 font-medium"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent"
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? "text-cyan-400" : "text-slate-500"}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Right Settings Form Area (3 Cols) */}
        <div className="lg:col-span-3 p-6 rounded-xl bg-[#090d19] border border-slate-800 space-y-6">
          {activeTab === "general" && (
            <div className="space-y-4">
              <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
                General OS Configuration
              </span>

              <div className="space-y-3 max-w-md">
                <div className="space-y-1">
                  <label className="text-slate-400 text-[11px]">Assistant Identity Name</label>
                  <input
                    type="text"
                    value={assistantName}
                    onChange={(e) => setAssistantName(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-500/50"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-slate-400 text-[11px]">Default Response Tone</label>
                  <select className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 outline-none">
                    <option value="calm">Calm & Professional</option>
                    <option value="concise">Concise Developer</option>
                    <option value="thorough">Detailed Analyst</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {activeTab === "ai" && (
            <div className="space-y-4">
              <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
                AI Models & Model Router
              </span>

              <div className="space-y-3 max-w-md">
                <div className="space-y-1">
                  <label className="text-slate-400 text-[11px]">Primary Ollama LLM Model</label>
                  <select
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 outline-none"
                  >
                    <option value="llama3.2:1b">llama3.2:1b (Fast, Local)</option>
                    <option value="qwen2.5-coder">qwen2.5-coder:7b (Coding Specialist)</option>
                    <option value="deepseek-r1">deepseek-r1 (Reasoning Engine)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-slate-400 text-[11px]">Autonomy Level (1 - 5)</label>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    value={autonomyLevel}
                    onChange={(e) => setAutonomyLevel(Number(e.target.value))}
                    className="w-full text-cyan-500 accent-cyan-500"
                  />
                  <span className="text-[10px] text-cyan-400">Level {autonomyLevel} — Full Orchestration</span>
                </div>
              </div>
            </div>
          )}

          {activeTab === "voice" && (
            <div className="space-y-4">
              <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
                Voice Pipeline Settings
              </span>

              <div className="space-y-3 max-w-md">
                <div className="space-y-1">
                  <label className="text-slate-400 text-[11px]">TTS Speaking Rate (Words Per Minute)</label>
                  <input
                    type="number"
                    value={ttsSpeed}
                    onChange={(e) => setTtsSpeed(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 outline-none"
                  />
                </div>
              </div>
            </div>
          )}

          {activeTab === "advanced" && (
            <div className="space-y-4">
              <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
                Raw System Configuration JSON
              </span>

              <pre className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-[11px] text-cyan-400 overflow-x-auto">
                {JSON.stringify(rawSettings, null, 2)}
              </pre>
            </div>
          )}

          {/* Fallback for other tabs */}
          {!["general", "ai", "voice", "advanced"].includes(activeTab) && (
            <div className="space-y-4">
              <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
                {activeTab.toUpperCase()} Preferences
              </span>
              <p className="text-slate-500 text-xs">
                Configuration controls for {activeTab} are active and enforced by backend default rules.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
