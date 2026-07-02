import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { nexoraApi, ProcessResult, StatusPayload, wsEventsUrl } from "../api/client";

type AgentRow = { name: string; status: string; tools?: string[] };
type WorkflowRow = { name: string; enabled: boolean; last_status?: string; step_count?: number };
type MemoryItem = { summary?: string; content?: string };
type BusEvent = { topic: string; payload: unknown; sequence: number };
type ModuleRow = { name: string; status: string; detail?: string };
export type AgentStep = { step: number; thought: string; action: string; params: Record<string, unknown>; timestamp: number };

type NexoraContextValue = {
  connected: boolean;
  status: StatusPayload | null;
  agents: { tool: AgentRow[]; runtime: AgentRow[] };
  workflows: WorkflowRow[];
  modules: ModuleRow[];
  memoryItems: MemoryItem[];
  memoryCount: number;
  events: BusEvent[];
  voiceState: string;
  lastMessage: string;
  pendingTaskId: string | null;
  busy: boolean;
  error: string | null;
  agentSteps: AgentStep[];
  pendingQuestion: string | null;
  sendCommand: (text: string, context?: Record<string, unknown>) => Promise<ProcessResult | null>;
  confirmPending: (yes: boolean) => Promise<void>;
  startVoice: () => Promise<void>;
  speak: (text: string) => Promise<void>;
  refreshMemory: (query?: string) => Promise<void>;
  visionStart: () => Promise<void>;
  visionStop: () => Promise<void>;
};

const NexoraContext = createContext<NexoraContextValue | null>(null);

export function NexoraProvider({ children }: { children: React.ReactNode }) {
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [agents, setAgents] = useState<{ tool: AgentRow[]; runtime: AgentRow[] }>({ tool: [], runtime: [] });
  const [workflows, setWorkflows] = useState<WorkflowRow[]>([]);
  const [modules, setModules] = useState<ModuleRow[]>([]);
  const [memoryItems, setMemoryItems] = useState<MemoryItem[]>([]);
  const [memoryCount, setMemoryCount] = useState(0);
  const [events, setEvents] = useState<BusEvent[]>([]);
  const [voiceState, setVoiceState] = useState("idle");
  const [lastMessage, setLastMessage] = useState("Awaiting command, Sir.");
  const [pendingTaskId, setPendingTaskId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);

  const refreshMemory = useCallback(async (query = "") => {
    try {
      const mem = await nexoraApi.memory(query, 10);
      setMemoryItems(mem.items ?? []);
      setMemoryCount(mem.count ?? 0);
    } catch (e) {
      console.warn("Could not refresh memory:", e);
    }
  }, []);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: number | null = null;
    let active = true;

    function connect() {
      if (!active) return;
      
      const wsUrl = wsEventsUrl();
      console.log(`[NexoraWebSocket] Connecting to ${wsUrl}...`);
      
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log("[NexoraWebSocket] Connected.");
        setConnected(true);
        setError(null);
        refreshMemory();
      };

      ws.onmessage = (event) => {
        if (!active) return;
        try {
          const data = JSON.parse(event.data);
          
          if (data.status) {
            setStatus(data.status);
            setVoiceState(data.status.voice_state ?? "idle");
          }

          if (data.state) {
            const ag = data.state.agents;
            if (ag) {
              setAgents({
                tool: ag.tool_agents ?? [],
                runtime: ag.runtime_agents ?? [],
              });
            }
            if (data.state.workflows) {
              setWorkflows(data.state.workflows);
            }
            if (data.state.modules) {
              setModules(data.state.modules);
            }
          }

          if (data.events && data.events.length > 0) {
            setEvents((prev) => {
              const combined = [...prev, ...data.events];
              // Deduplicate by sequence
              const seen = new Set<number>();
              const unique: BusEvent[] = [];
              for (let i = combined.length - 1; i >= 0; i--) {
                const ev = combined[i];
                if (!seen.has(ev.sequence)) {
                  seen.add(ev.sequence);
                  unique.unshift(ev);
                }
              }
              // Check if memory needs update
              const hasMemoryUpdate = data.events.some((e: BusEvent) => 
                e.topic.startsWith("memory.") || e.topic.startsWith("state.memory")
              );
              if (hasMemoryUpdate) {
                refreshMemory();
              }
              // Extract autonomous agent step events
              for (const ev of data.events) {
                if (ev.topic === "agent.step") {
                  const p = ev.payload as Record<string, unknown>;
                  setAgentSteps((prev) => [
                    ...prev.slice(-19),
                    { step: p.step as number, thought: p.thought as string, action: p.action as string, params: (p.params ?? {}) as Record<string, unknown>, timestamp: Date.now() }
                  ]);
                } else if (ev.topic === "agent.ask_user") {
                  const p = ev.payload as Record<string, unknown>;
                  setPendingQuestion(p.question as string);
                }
              }
              return unique.slice(-60);
            });
          }
        } catch (e) {
          console.error("[NexoraWebSocket] Message parsing error:", e);
        }
      };

      ws.onclose = (event) => {
        if (!active) return;
        console.warn(`[NexoraWebSocket] Disconnected: code=${event.code}, reason=${event.reason}. Retrying in 3s...`);
        setConnected(false);
        setError("Connection lost. Reconnecting...");
        reconnectTimeout = window.setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.error("[NexoraWebSocket] Socket error:", err);
        setConnected(false);
      };
    }

    connect();

    return () => {
      active = false;
      if (ws) {
        ws.close();
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
    };
  }, [refreshMemory]);

  const sendCommand = useCallback(
    async (text: string, context: Record<string, unknown> = {}) => {
      if (!text.trim()) return null;
      setBusy(true);
      setError(null);
      setAgentSteps([]);  // Clear previous steps on new command
      setPendingQuestion(null);
      try {
        const result = await nexoraApi.process(text.trim(), {
          ...context,
          speak: context.mode === "voice",
        });
        if (result.type === "confirmation_required" && result.task_id) {
          setPendingTaskId(result.task_id);
          setLastMessage(result.message ?? "Confirmation required.");
        } else {
          setPendingTaskId(null);
          setLastMessage(result.message ?? "Done.");
        }
        return result;
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Command failed";
        setError(msg);
        setLastMessage(msg);
        return null;
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const confirmPending = useCallback(
    async (yes: boolean) => {
      if (!pendingTaskId) return;
      setBusy(true);
      try {
        const result = await nexoraApi.confirm(pendingTaskId, yes);
        setPendingTaskId(null);
        setLastMessage(result.message ?? (yes ? "Confirmed." : "Cancelled."));
      } finally {
        setBusy(false);
      }
    },
    [pendingTaskId],
  );

  const startVoice = useCallback(async () => {
    setBusy(true);
    try {
      const listen = await nexoraApi.voiceListen(12);
      const text = listen.text?.trim();
      if (text) {
        await sendCommand(text, { mode: "voice" });
      } else {
        setLastMessage(listen.error ?? "Didn't catch that.");
      }
    } finally {
      setBusy(false);
    }
  }, [sendCommand]);

  const speak = useCallback(async (text: string) => {
    await nexoraApi.voiceSpeak(text);
  }, []);

  const visionStart = useCallback(async () => {
    await nexoraApi.visionStart();
  }, []);

  const visionStop = useCallback(async () => {
    await nexoraApi.visionStop();
  }, []);

  const value = useMemo(
    () => ({
      connected,
      status,
      agents,
      workflows,
      modules,
      memoryItems,
      memoryCount,
      events,
      voiceState,
      lastMessage,
      pendingTaskId,
      busy,
      error,
      agentSteps,
      pendingQuestion,
      sendCommand,
      confirmPending,
      startVoice,
      speak,
      refreshMemory,
      visionStart,
      visionStop,
    }),
    [
      connected,
      status,
      agents,
      workflows,
      modules,
      memoryItems,
      memoryCount,
      events,
      voiceState,
      lastMessage,
      pendingTaskId,
      busy,
      error,
      agentSteps,
      pendingQuestion,
      sendCommand,
      confirmPending,
      startVoice,
      speak,
      refreshMemory,
      visionStart,
      visionStop,
    ],
  );

  return <NexoraContext.Provider value={value}>{children}</NexoraContext.Provider>;
}

export function useNexora() {
  const ctx = useContext(NexoraContext);
  if (!ctx) throw new Error("useNexora must be used within NexoraProvider");
  return ctx;
}
