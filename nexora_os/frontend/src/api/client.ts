const API_BASE = import.meta.env.VITE_NEXORA_API ?? "http://127.0.0.1:7474";

export type ProcessResult = {
  type: string;
  message?: string;
  task_id?: string;
  plan?: unknown[];
  steps?: unknown[];
};

export type HealthSnapshot = {
  ok?: boolean;
  snapshot?: {
    cpu_percent?: number;
    memory_percent?: number;
    gpu?: { utilization?: number; cuda?: boolean; name?: string };
    modules?: Record<string, { name: string; status: string; detail?: string }>;
    voice?: { status?: string; speaking?: boolean };
    event_bus?: {
      events_per_sec?: number;
      subscriber_error_count?: number;
      queue_size?: number;
    };
    agents?: unknown[];
    workflows?: unknown[];
  };
};

export type StatusPayload = {
  llm_ready: boolean;
  voice_ready: boolean;
  memory_ready: boolean;
  voice_state?: string;
  cpu: number;
  ram: number;
  gpu?: { utilization?: number };
  tasks: number;
  memories: number;
  modules: number;
  event_errors: number;
  events_per_sec: number;
  active_agents?: number;
  active_workflows?: number;
  process_memory_mb?: number;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const nexoraApi = {
  baseUrl: API_BASE,

  async ping(): Promise<boolean> {
    try {
      await request<StatusPayload>("/status");
      return true;
    } catch {
      return false;
    }
  },

  status: () => request<StatusPayload>("/status"),
  health: () => request<HealthSnapshot>("/health"),
  state: () => request<Record<string, unknown>>("/state"),
  events: (limit = 60) => request<{ events: Array<{ topic: string; payload: unknown; sequence: number }> }>(`/events?limit=${limit}`),
  agents: () => request<{ tool_agents: Array<{ name: string; status: string; tools?: string[] }>; runtime_agents: Array<{ name: string; status: string }> }>("/agents"),
  workflows: () => request<{ workflows: Array<{ name: string; enabled: boolean; last_status?: string; step_count?: number }> }>("/workflows"),
  memory: (query = "", limit = 8) => request<{ count: number; items: Array<{ summary?: string; content?: string }> }>(`/memory?query=${encodeURIComponent(query)}&limit=${limit}`),

  process: (input: string, context: Record<string, unknown> = {}) =>
    request<ProcessResult>("/process", {
      method: "POST",
      body: JSON.stringify({ input, context }),
    }),

  confirm: (task_id: string, confirmed: boolean) =>
    request<ProcessResult>("/confirm", {
      method: "POST",
      body: JSON.stringify({ task_id, confirmed }),
    }),

  voiceListen: (timeout = 12) =>
    request<{ text?: string; error?: string; ok?: boolean }>(`/voice/listen?timeout=${timeout}`, { method: "POST" }),

  voiceSpeak: (text: string) =>
    request<{ ok?: boolean }>("/voice/speak", {
      method: "POST",
      body: JSON.stringify({ text, interrupt: true }),
    }),

  visionStart: () => request<Record<string, unknown>>("/vision/webcam/start", { method: "POST" }),
  visionStop: () => request<Record<string, unknown>>("/vision/webcam/stop", { method: "POST" }),
  visionStatus: () => request<Record<string, unknown>>("/vision/status"),
  visionCapture: () => request<Record<string, unknown>>("/vision/capture", { method: "POST" }),

  listGraphs: () => request<{ graphs: Array<{ name: string; node_count: number; edge_count: number }> }>("/workflows/graphs"),
  getGraph: (name: string) => request<GraphSpec>(`/workflows/graph/${encodeURIComponent(name)}`),
  saveGraph: (spec: GraphSpec) =>
    request<{ ok: boolean; name: string }>("/workflows/graph/save", {
      method: "POST",
      body: JSON.stringify(spec),
    }),
  runGraph: (name: string) =>
    request<Record<string, unknown>>(`/workflows/graph/run/${encodeURIComponent(name)}`, { method: "POST" }),
  generateWorkflow: (description: string) =>
    request<{ spec?: GraphSpec; generated?: boolean }>("/workflows/generate", {
      method: "POST",
      body: JSON.stringify({ description }),
    }),
  workflowTrace: (name: string, runId?: string) =>
    request<{ trace: TraceStep[] }>(
      `/workflows/trace/${encodeURIComponent(name)}${runId ? `?run_id=${runId}` : ""}`,
    ),

  memoryStore: (text: string, memory_type = "semantic", tags: string[] = []) =>
    request<Record<string, unknown>>("/memory/store", {
      method: "POST",
      body: JSON.stringify({ text, memory_type, tags }),
    }),
  memorySearch: (q: string, limit = 10) =>
    request<{ items: MemoryHit[] }>(`/memory/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  memoryNetwork: () => request<{ nodes: NetworkNode[]; edges: NetworkEdge[] }>("/memory/network"),
  memoryReflect: (query = "") =>
    request<{ reflection: string; memory_ids: number[] }>(`/memory/reflect?query=${encodeURIComponent(query)}`, { method: "POST" }),

  agentTask: (name: string, task: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/agents/${encodeURIComponent(name)}/tasks`, {
      method: "POST",
      body: JSON.stringify({ task }),
    }),
  automation: () => request<{ registered_actions: string[]; history: Array<Record<string, unknown>> }>("/automation"),
  automationRun: (input: string) =>
    request<Record<string, unknown>>("/automation/run", {
      method: "POST",
      body: JSON.stringify({ input, context: {} }),
    }),
  settings: () => request<Record<string, unknown>>("/settings"),
  voiceStatus: () => request<Record<string, unknown>>("/voice/status"),
  visionScreen: (ocr = true) =>
    request<Record<string, unknown>>(`/vision/screen?ocr=${ocr}`, { method: "POST" }),

  nodeTypes: () => request<{ node_types: string[] }>("/platform/node-types"),
};

export type GraphSpec = {
  name: string;
  description?: string;
  graph: {
    nodes: Array<{ id: string; type: string; data?: Record<string, unknown>; position?: { x: number; y: number } }>;
    edges: Array<{ id: string; source: string; target: string }>;
  };
};

export type TraceStep = {
  node_id: string;
  node_type: string;
  status: string;
  duration_ms?: number;
  error?: string;
};

export type MemoryHit = { text: string; score?: number; metadata?: Record<string, unknown>; source?: string };
export type NetworkNode = { id: string; label: string; type?: string };
export type NetworkEdge = { source: string; target: string };

export function wsEventsUrl(): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/ws/events`;
}
