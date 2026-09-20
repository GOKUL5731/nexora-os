import React, { useEffect, useState } from "react";
import { TopBar } from "./components/TopBar";
import { Sidebar } from "./components/Sidebar";
import { RightPanel } from "./components/RightPanel";
import { BrainView } from "./components/BrainView";
import { NexoraProvider, useNexora } from "../context/NexoraContext";
import { Scene3D } from "./components/3d/Scene3D";

import { DashboardPage } from "./components/pages/DashboardPage";
import { ChatPage } from "./components/pages/ChatPage";
import { ProjectsPage } from "./components/pages/ProjectsPage";
import { KnowledgePage } from "./components/pages/KnowledgePage";
import { MemoryPage } from "./components/pages/MemoryPage";
import { AgentsPage } from "./components/pages/AgentsPage";
import { WorkflowStudio } from "./components/workflow/WorkflowStudio";
import { AutomationPage } from "./components/pages/AutomationPage";
import { VisionPage } from "./components/pages/VisionPage";
import { VoicePage } from "./components/pages/VoicePage";
import { ConnectorsPage } from "./components/pages/ConnectorsPage";
import { LabPage } from "./components/pages/LabPage";
import { SettingsPage } from "./components/pages/SettingsPage";
import { CompanionPage } from "./components/pages/CompanionPage";
import { PetGPage } from "./components/pages/PetGPage";

import { motion, AnimatePresence } from "motion/react";
import "../styles/custom.css";

function AppShell() {
  const initialTab = typeof window !== "undefined" ? window.location.hash.replace("#", "") || "dashboard" : "dashboard";
  const [activeTab, setActiveTab] = useState(initialTab);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [commandSearchOpen, setCommandSearchOpen] = useState(false);

  useEffect(() => {
    if (window.location.hash.replace("#", "") !== activeTab) {
      window.history.replaceState(null, "", `#${activeTab}`);
    }
  }, [activeTab]);

  const renderTab = () => {
    switch (activeTab) {
      case "dashboard":
      case "home":
        return <DashboardPage onNavigate={setActiveTab} />;
      case "chat":
        return <ChatPage />;
      case "brain":
        return <div className="w-full h-full flex items-center justify-center">
          <BrainView />
        </div>;
      case "projects":
        return <ProjectsPage />;
      case "knowledge":
        return <KnowledgePage />;
      case "memory":
        return <MemoryPage />;
      case "agents":
        return <AgentsPage />;
      case "workflows":
        return <WorkflowStudio />;
      case "automation":
        return <AutomationPage />;
      case "vision":
        return <VisionPage />;
      case "voice":
        return <VoicePage />;
      case "connectors":
        return <ConnectorsPage />;
      case "lab":
        return <LabPage />;
      case "settings":
        return <SettingsPage />;
      case "companion":
        return <CompanionPage />;
      case "pet-g":
        return <PetGPage />;
      default:
        return <DashboardPage onNavigate={setActiveTab} />;
    }
  };

  return (
    <div className="g-os-shell w-full h-screen text-slate-100 overflow-hidden flex flex-col font-sans relative">
      {/* 3D Background Scene */}
      <Scene3D />

      {/* Top Header Bar */}
      <TopBar
        activeTab={activeTab}
        rightPanelOpen={rightPanelOpen}
        setRightPanelOpen={setRightPanelOpen}
        onOpenCommandSearch={() => setCommandSearchOpen(true)}
      />

      {/* Main 3-Column Layout */}
      <div className="g-workbench flex-1 flex min-h-0 relative overflow-hidden pointer-events-none">
        {/* Left Column: Navigation Sidebar */}
        <div className="pointer-events-auto">
          <Sidebar
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            collapsed={sidebarCollapsed}
            setCollapsed={setSidebarCollapsed}
          />
        </div>

        {/* Center Column: Workspace View */}
        <main className="g-main-surface flex-1 flex flex-col min-w-0 relative overflow-hidden pointer-events-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              className="flex-1 flex flex-col overflow-hidden h-full"
            >
              {renderTab()}
            </motion.div>
          </AnimatePresence>
        </main>

        {/* Right Column: Context Panel */}
        <div className="pointer-events-auto">
          <RightPanel open={rightPanelOpen} />
        </div>
      </div>

      {/* Command Search Modal (Cmd+K) */}
      {commandSearchOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center pt-20 p-4">
          <div className="w-full max-w-xl bg-[#0d1322] border border-slate-700 rounded-xl shadow-2xl overflow-hidden font-mono text-xs">
            <div className="p-3 border-b border-slate-800 flex items-center justify-between">
              <span className="text-slate-300 font-semibold uppercase">Command Palette</span>
              <button
                onClick={() => setCommandSearchOpen(false)}
                className="text-slate-500 hover:text-slate-300 px-2 py-0.5 rounded"
              >
                ESC
              </button>
            </div>
            <div className="p-3 space-y-1">
              <button
                onClick={() => {
                  setActiveTab("chat");
                  setCommandSearchOpen(false);
                }}
                className="w-full text-left p-2.5 rounded hover:bg-slate-800/80 text-slate-300 flex items-center justify-between"
              >
                <span>Open Chat Workspace</span>
                <span className="text-[10px] text-slate-500">Navigation</span>
              </button>
              <button
                onClick={() => {
                  setActiveTab("knowledge");
                  setCommandSearchOpen(false);
                }}
                className="w-full text-left p-2.5 rounded hover:bg-slate-800/80 text-slate-300 flex items-center justify-between"
              >
                <span>Search Knowledge Base</span>
                <span className="text-[10px] text-slate-500">Navigation</span>
              </button>
              <button
                onClick={() => {
                  setActiveTab("memory");
                  setCommandSearchOpen(false);
                }}
                className="w-full text-left p-2.5 rounded hover:bg-slate-800/80 text-slate-300 flex items-center justify-between"
              >
                <span>Open Memory DB</span>
                <span className="text-[10px] text-slate-500">Navigation</span>
              </button>
            </div>
          </div>
        </div>
      )}
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
