import React, { useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { CognitiveOrb } from "./components/CognitiveOrb";
import { RightPanel } from "./components/RightPanel";
import { LowerPanels } from "./components/LowerPanels";
import { BrainView } from "./components/BrainView";
import { CommandBar } from "./components/CommandBar";
import { NexoraProvider } from "../context/NexoraContext";
import { VoicePage } from "./components/pages/VoicePage";
import { VisionPage } from "./components/pages/VisionPage";
import { AgentsPage } from "./components/pages/AgentsPage";
import { WorkflowStudio } from "./components/workflow/WorkflowStudio";
import { MemoryPage } from "./components/pages/MemoryPage";
import { AutomationPage } from "./components/pages/AutomationPage";
import { LabPage } from "./components/pages/LabPage";
import { SettingsPage } from "./components/pages/SettingsPage";
import { useNexora } from "../context/NexoraContext";
import { motion, AnimatePresence } from "motion/react";
import "../styles/custom.css";

function AppShell() {
  const [activeTab, setActiveTab] = useState("home");
  const { connected, error } = useNexora();

  const renderTab = () => {
    switch (activeTab) {
      case "home":
        return (
          <>
            <CognitiveOrb />
            <CommandBar className="absolute bottom-[42%] left-0 right-0 z-20" />
            <LowerPanels />
          </>
        );
      case "brain":
        return <BrainView />;
      case "voice":
        return <VoicePage />;
      case "vision":
        return <VisionPage />;
      case "agents":
        return <AgentsPage />;
      case "workflows":
        return <WorkflowStudio />;
      case "automation":
        return <AutomationPage />;
      case "memory":
        return <MemoryPage />;
      case "lab":
        return <LabPage />;
      case "settings":
        return <SettingsPage />;
      default:
        return null;
    }
  };

  return (
    <div className="w-full h-screen bg-[#010308] text-white overflow-hidden flex font-sans selection:bg-cyan-500/30">
      <div className="absolute inset-0 z-0">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[100vw] md:w-[1000px] h-[100vw] md:h-[1000px] bg-[radial-gradient(circle_at_center,rgba(0,180,255,0.03)_0%,transparent_60%)] rounded-full blur-3xl pointer-events-none" />
        <div className="absolute inset-0 opacity-10 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI1MCIgaGVpZ2h0PSI4Ni42Ij48cGF0aCBkPSJNMjUgMGwyNSAxNC40djI4LjhMMjUgNTcuNkwwIDQzLjJWMTRuNHpNMjUgODYuNmwyNS0xNC40VjQzLjRsLTI1IDE0LjRMMCA0My40djI4Ljh6IiBmaWxsPSJub25lIiBzdHJva2U9IiMwNmI2ZDQiIHN0cm9rZS13aWR0aD0iMSIvPjwvc3ZnPg==')] bg-[length:30px_52px] pointer-events-none" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_30%,#010308_100%)] pointer-events-none" />
      </div>

      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} connected={connected} />

      <div className="flex-1 flex flex-col relative z-10 h-full overflow-hidden">
        <header className="h-16 flex items-center px-4 md:px-8 border-b border-cyan-900/20 bg-black/20 backdrop-blur-sm">
          <div className="flex items-center gap-4 text-xs font-['Rajdhani'] tracking-[0.2em] uppercase text-cyan-500">
            <span>SYSTEM</span>
            <span className="text-cyan-800">/</span>
            <span className="text-cyan-100">{activeTab}</span>
          </div>
          <div className="ml-auto flex items-center gap-4 text-[10px] font-mono">
            <span className={connected ? "text-cyan-400" : "text-red-400/80"}>
              {connected ? "BACKEND ONLINE" : "BACKEND OFFLINE"}
            </span>
            {error && <span className="text-red-400/70 truncate max-w-[200px]">{error}</span>}
            <span className="text-cyan-600/50">
              {new Date().toISOString().split("T")[0].replace(/-/g, ".")}
            </span>
          </div>
        </header>

        <div className="flex-1 flex flex-col min-h-0 relative">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.02 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className="flex-1 flex flex-col overflow-hidden"
            >
              {renderTab()}
            </motion.div>
          </AnimatePresence>
          <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(rgba(0,0,0,0)_50%,rgba(0,0,0,0.1)_50%)] bg-[length:100%_4px] opacity-20" />
        </div>
      </div>

      <RightPanel />
    </div>
  );
}

export default function App() {
  return (
    <NexoraProvider>
      <AppShell />
    </NexoraProvider>
  );
}
