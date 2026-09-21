import React, { lazy, Suspense, useEffect, useState } from "react";
import { RightPanel } from "./components/RightPanel";
import { NexoraProvider, useNexora } from "../context/NexoraContext";

import { motion, AnimatePresence } from "motion/react";
import {
  Activity,
  Bot,
  BookOpenCheck,
  Brain,
  Boxes,
  Command,
  Database,
  Fingerprint,
  FolderGit2,
  Gauge,
  Home,
  Menu,
  MessageSquare,
  Mic,
  Network,
  PanelRight,
  PlugZap,
  Search,
  Settings,
  Shield,
  Sparkles,
  Telescope,
  Video,
  Workflow,
  X,
  Zap,
} from "lucide-react";
import "../styles/custom.css";

const Scene3D = lazy(() => import("./components/3d/Scene3D").then((module) => ({ default: module.Scene3D })));
const BrainView = lazy(() => import("./components/BrainView").then((module) => ({ default: module.BrainView })));
const DashboardPage = lazy(() => import("./components/pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const ChatPage = lazy(() => import("./components/pages/ChatPage").then((module) => ({ default: module.ChatPage })));
const ProjectsPage = lazy(() => import("./components/pages/ProjectsPage").then((module) => ({ default: module.ProjectsPage })));
const KnowledgePage = lazy(() => import("./components/pages/KnowledgePage").then((module) => ({ default: module.KnowledgePage })));
const MemoryPage = lazy(() => import("./components/pages/MemoryPage").then((module) => ({ default: module.MemoryPage })));
const AgentsPage = lazy(() => import("./components/pages/AgentsPage").then((module) => ({ default: module.AgentsPage })));
const WorkflowStudio = lazy(() => import("./components/workflow/WorkflowStudio").then((module) => ({ default: module.WorkflowStudio })));
const AutomationPage = lazy(() => import("./components/pages/AutomationPage").then((module) => ({ default: module.AutomationPage })));
const VisionPage = lazy(() => import("./components/pages/VisionPage").then((module) => ({ default: module.VisionPage })));
const VoicePage = lazy(() => import("./components/pages/VoicePage").then((module) => ({ default: module.VoicePage })));
const ConnectorsPage = lazy(() => import("./components/pages/ConnectorsPage").then((module) => ({ default: module.ConnectorsPage })));
const LabPage = lazy(() => import("./components/pages/LabPage").then((module) => ({ default: module.LabPage })));
const SettingsPage = lazy(() => import("./components/pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));
const CompanionPage = lazy(() => import("./components/pages/CompanionPage").then((module) => ({ default: module.CompanionPage })));
const PetGPage = lazy(() => import("./components/pages/PetGPage").then((module) => ({ default: module.PetGPage })));
const SecurityPage = lazy(() => import("./components/pages/SecurityPage").then((module) => ({ default: module.SecurityPage })));
const MCPPage = lazy(() => import("./components/pages/MCPPage").then((module) => ({ default: module.MCPPage })));
const LearningPage = lazy(() => import("./components/pages/LearningPage").then((module) => ({ default: module.LearningPage })));
const PluginsPage = lazy(() => import("./components/pages/PluginsPage").then((module) => ({ default: module.PluginsPage })));
const DeveloperPage = lazy(() => import("./components/pages/DeveloperPage").then((module) => ({ default: module.DeveloperPage })));
const ComputerControlPage = lazy(() => import("./components/pages/ComputerControlPage").then((module) => ({ default: module.ComputerControlPage })));

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
  { id: "computer", label: "Control", icon: Fingerprint, group: "Build" },
  { id: "vision", label: "Vision", icon: Video, group: "Senses" },
  { id: "voice", label: "Voice", icon: Mic, group: "Senses" },
  { id: "connectors", label: "Links", icon: Boxes, group: "Senses" },
  { id: "learning", label: "Learn", icon: BookOpenCheck, group: "System" },
  { id: "mcp", label: "MCP", icon: PlugZap, group: "System" },
  { id: "plugins", label: "Plugins", icon: Boxes, group: "System" },
  { id: "security", label: "Security", icon: Shield, group: "System" },
  { id: "developer", label: "Dev", icon: Command, group: "System" },
  { id: "lab", label: "Lab", icon: Sparkles, group: "System" },
  { id: "settings", label: "Settings", icon: Settings, group: "System" },
];

function LensFallback({ label }: { label: string }) {
  return (
    <div className="g2-lens-loading" role="status" aria-live="polite">
      <span />
      <strong>Opening {label}</strong>
      <small>Loading this lens only when requested.</small>
    </div>
  );
}

function AppShell() {
  const { connected, status, brainState, busy, gCoreState, lowPowerMode, reducedMotion, setLowPowerMode } = useNexora();
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
      case "computer":
        return <ComputerControlPage />;
      case "vision":
        return <VisionPage />;
      case "voice":
        return <VoicePage />;
      case "connectors":
        return <ConnectorsPage />;
      case "learning":
        return <LearningPage />;
      case "mcp":
        return <MCPPage />;
      case "plugins":
        return <PluginsPage />;
      case "security":
        return <SecurityPage />;
      case "developer":
        return <DeveloperPage />;
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
      {lowPowerMode ? (
        <div className="g2-spatial-fallback" aria-hidden="true">
          <div className={`g2-static-core state-${gCoreState.toLowerCase()}`} />
        </div>
      ) : (
        <Suspense fallback={<div className="g2-spatial-fallback" aria-hidden="true" />}>
          <Scene3D />
        </Suspense>
      )}

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
          <button
            onClick={() => setLowPowerMode(!lowPowerMode)}
            aria-pressed={lowPowerMode}
            aria-label={lowPowerMode ? "Disable low power visuals" : "Enable low power visuals"}
            title={reducedMotion ? "OS reduced motion is active" : lowPowerMode ? "Low power visuals on" : "Full spatial visuals on"}
          >
            <Gauge className="h-4 w-4" />
          </button>
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
              <Suspense fallback={<LensFallback label={activeNav.label} />}>
                {renderTab()}
              </Suspense>
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
