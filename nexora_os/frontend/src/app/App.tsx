import React, { useEffect, useState } from "react";
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
import {
  Activity,
  Bot,
  Brain,
  Boxes,
  Command,
  Database,
  FolderGit2,
  Home,
  Menu,
  MessageSquare,
  Mic,
  Network,
  PanelRight,
  Search,
  Settings,
  Sparkles,
  Telescope,
  Video,
  Workflow,
  X,
  Zap,
} from "lucide-react";
import "../styles/custom.css";

const EXPERIENCE_NAV = [
  { id: "dashboard", label: "Home", icon: Home, group: "Start" },
  { id: "chat", label: "Talk", icon: MessageSquare, group: "Create" },
  { id: "pet-g", label: "Pet G", icon: Bot, group: "Create" },
  { id: "brain", label: "Brain", icon: Brain, group: "Core" },
  { id: "memory", label: "Memory", icon: Database, group: "Core" },
  { id: "knowledge", label: "Knowledge", icon: Telescope, group: "Core" },
  { id: "projects", label: "Projects", icon: FolderGit2, group: "Build" },
  { id: "agents", label: "Agents", icon: Network, group: "Build" },
  { id: "workflows", label: "Flows", icon: Workflow, group: "Build" },
  { id: "automation", label: "Actions", icon: Zap, group: "Build" },
  { id: "vision", label: "Vision", icon: Video, group: "Senses" },
  { id: "voice", label: "Voice", icon: Mic, group: "Senses" },
  { id: "connectors", label: "Links", icon: Boxes, group: "Senses" },
  { id: "lab", label: "Lab", icon: Sparkles, group: "System" },
  { id: "settings", label: "Settings", icon: Settings, group: "System" },
];

function AppShell() {
  const { connected, status, brainState, busy, gCoreState } = useNexora();
  const initialTab = typeof window !== "undefined" ? window.location.hash.replace("#", "") || "dashboard" : "dashboard";
  const [activeTab, setActiveTab] = useState(initialTab);
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [commandSearchOpen, setCommandSearchOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    if (window.location.hash.replace("#", "") !== activeTab) {
      window.history.replaceState(null, "", `#${activeTab}`);
    }
  }, [activeTab]);

  const activeNav = EXPERIENCE_NAV.find((item) => item.id === activeTab) ?? EXPERIENCE_NAV[0];
  const ActiveIcon = activeNav.icon;

  const navigate = (tab: string) => {
    setActiveTab(tab);
    setCommandSearchOpen(false);
    setNavOpen(false);
  };

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
    <div className="g2-os-shell">
      <Scene3D />

      <header className="g2-command-strip">
        <button className="g2-round-button" onClick={() => setNavOpen((value) => !value)} aria-label="Open navigation">
          {navOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </button>
        <div className="g2-identity">
          <span>G</span>
          <div>
            <strong>NEXORA</strong>
            <small>{brainState?.current_goal || "Personal cognitive operating layer"}</small>
          </div>
        </div>
        <button className="g2-search-trigger" onClick={() => setCommandSearchOpen(true)}>
          <Search className="h-4 w-4" />
          Ask, jump, or open a lens
          <kbd>⌘K</kbd>
        </button>
        <div className="g2-system-pills">
          <span className={connected ? "online" : "offline"}>
            <Activity className="h-3.5 w-3.5" />
            {connected ? "Live" : "Offline"}
          </span>
          <span>{connected ? gCoreState : busy ? "THINKING" : "READY"}</span>
          <button onClick={() => setRightPanelOpen((value) => !value)} aria-label="Toggle system context">
            <PanelRight className="h-4 w-4" />
          </button>
        </div>
      </header>

      <div className={`g2-lens-map ${navOpen ? "open" : ""}`} aria-hidden={!navOpen}>
        {["Start", "Create", "Core", "Build", "Senses", "System"].map((group) => (
          <section key={group}>
            <p>{group}</p>
            <div>
              {EXPERIENCE_NAV.filter((item) => item.group === group).map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => navigate(item.id)}
                    className={activeTab === item.id ? "active" : ""}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </button>
                );
              })}
            </div>
          </section>
        ))}
      </div>

      <section className="g2-stage">
        <aside className="g2-left-rail">
          <div className="g2-orbital-status">
            <ActiveIcon className="h-5 w-5" />
            <span>{activeNav.group}</span>
            <strong>{activeNav.label}</strong>
          </div>
          <div className="g2-runtime-card">
            <small>Runtime</small>
            <strong>{connected ? "Connected" : "Local backend offline"}</strong>
            <span>CPU {Math.round(status?.cpu ?? 0)} · RAM {Math.round(status?.ram ?? 0)}</span>
          </div>
        </aside>

        <main className="g2-workspace">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, scale: 0.985, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.99, y: -8 }}
              transition={{ duration: 0.24, ease: "easeOut" }}
              className="g2-page-mount"
            >
              {renderTab()}
            </motion.div>
          </AnimatePresence>
        </main>

        <aside className={`g2-context-drawer ${rightPanelOpen ? "open" : ""}`}>
          <RightPanel open={rightPanelOpen} />
        </aside>
      </section>

      <nav className="g2-floating-dock" aria-label="Primary lens navigation">
        {EXPERIENCE_NAV.slice(0, 10).map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => navigate(item.id)}
              className={activeTab === item.id ? "active" : ""}
              aria-label={item.label}
              title={item.label}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {commandSearchOpen && (
        <div className="g2-command-modal">
          <div className="g2-command-card">
            <div>
              <span><Command className="h-4 w-4" /> Lens switcher</span>
              <button
                onClick={() => setCommandSearchOpen(false)}
                aria-label="Close command palette"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="g2-command-grid">
              {EXPERIENCE_NAV.map((item) => {
                const Icon = item.icon;
                return (
                  <button key={item.id} onClick={() => navigate(item.id)}>
                    <Icon className="h-4 w-4" />
                    <span>{item.label}</span>
                    <small>{item.group}</small>
                  </button>
                );
              })}
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
