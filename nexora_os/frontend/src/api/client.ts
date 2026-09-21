const API_BASE = import.meta.env.VITE_NEXORA_API ?? (import.meta.env.DEV ? "http://127.0.0.1:7474" : window.location.origin);

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
  brainStatus: () => request<Record<string, unknown>>("/brain/status"),
  cognitionStatus: () => request<CognitionStatus>("/cognition/status"),
  cognitionPerceive: (input: { type: string; content?: string; path?: string; source?: string; remember?: boolean }) =>
    request<Record<string, unknown>>("/cognition/perceive", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  capabilities: () => request<Record<string, unknown>>("/capabilities"),
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
  visionFrame: () => request<Record<string, unknown>>("/vision/frame", { method: "POST" }),
  visionFrameWithMouse: () => request<Record<string, unknown>>("/vision/frame/mouse", { method: "POST" }),
  visionMouseEnable: () => request<Record<string, unknown>>("/vision/mouse/enable", { method: "POST" }),
  visionMouseDisable: () => request<Record<string, unknown>>("/vision/mouse/disable", { method: "POST" }),
  visionMouseState: () => request<Record<string, unknown>>("/vision/mouse/state"),
  visionGesturesEnable: () => request<Record<string, unknown>>("/vision/gestures/enable", { method: "POST" }),
  visionGesturesDisable: () => request<Record<string, unknown>>("/vision/gestures/disable", { method: "POST" }),
  visionGesturesCapture: () => request<Record<string, unknown>>("/vision/gestures/capture", { method: "POST" }),
  visionGesturesState: () => request<Record<string, unknown>>("/vision/gestures/state"),

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

  knowledge: () =>
    request<{
      status: { domains: number; entries: number; database: string };
      domains: Array<{ name: string; status: string; summary: string; sources: string[]; updated_at?: number }>;
    }>("/knowledge"),
  knowledgeLearn: (domain: string) =>
    request<Record<string, unknown>>(`/knowledge/learn/${encodeURIComponent(domain)}`, { method: "POST" }),
  knowledgeSearch: (q: string, domain = "", limit = 8) =>
    request<{ items: KnowledgeHit[] }>(
      `/knowledge/search?q=${encodeURIComponent(q)}&domain=${encodeURIComponent(domain)}&limit=${limit}`,
    ),
  knowledgeIndex: (domain: string, title: string, content: string, source = "user provided", tags: string[] = []) =>
    request<Record<string, unknown>>("/knowledge/index", {
      method: "POST",
      body: JSON.stringify({ domain, title, content, source, tags }),
    }),
  learningJobs: (limit = 20) =>
    request<{ status: Record<string, unknown>; jobs: LearningJob[] }>(`/learning/jobs?limit=${limit}`),
  learningStart: (domain: string, goal = "", resources: Array<Record<string, unknown>> = [], expected_terms: string[] = []) =>
    request<Record<string, unknown>>("/learning/jobs", {
      method: "POST",
      body: JSON.stringify({ domain, goal, resources, expected_terms }),
    }),

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
  securityStatus: () => request<SecurityStatus>("/security/status"),
  securityAudit: (limit = 50) => request<{ items: SecurityAuditItem[] }>(`/security/audit?limit=${limit}`),
  securityEmergencyStop: (reason = "user_requested") =>
    request<Record<string, unknown>>("/security/emergency-stop", {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  securityEmergencyClear: () => request<Record<string, unknown>>("/security/emergency-stop/clear", { method: "POST" }),
  mcpStatus: () => request<Record<string, unknown>>("/mcp/status"),
  mcpTools: () => request<{ tools: MCPTool[] }>("/mcp/tools"),
  plugins: () => request<PluginRegistryStatus>("/plugins"),
  settings: () => request<Record<string, unknown>>("/settings"),
  voiceStatus: () => request<Record<string, unknown>>("/voice/status"),
  livekitStatus: () => request<Record<string, unknown>>("/realtime/livekit/status"),
  livekitToken: (room = "jarvis-ai", identity = "jarvis-user", name = "Jarvis User") =>
    request<Record<string, unknown>>("/realtime/livekit/token", {
      method: "POST",
      body: JSON.stringify({ room, identity, name }),
    }),
  visionScreen: (ocr = true) =>
    request<Record<string, unknown>>(`/vision/screen?ocr=${ocr}`, { method: "POST" }),

  nodeTypes: () => request<{ node_types: string[] }>("/platform/node-types"),

  connectors: () => request<{ connectors: Array<{ name: string; health: string; capabilities: string[] }>; available: number }>("/connectors"),
  orchestrationProjects: () => request<{ projects: OrchestrationProject[]; count: number }>("/orchestration/projects"),
  connectorExecute: (name: string, action: string, params: Record<string, unknown> = {}) =>
    request<Record<string, unknown>>(`/connectors/${encodeURIComponent(name)}/execute`, {
      method: "POST",
      body: JSON.stringify({ input: action, context: { action, ...params } }),
    }),

  companionStatus: () => request<Record<string, unknown>>("/companion/status"),
  companionPair: (deviceId: string, deviceName: string) =>
    request<Record<string, unknown>>("/companion/pair", {
      method: "POST",
      body: JSON.stringify({ device_id: deviceId, device_name: deviceName, platform: "iOS" }),
    }),
  companionSync: (deviceId: string, token: string, clipboard = "", location = {}) =>
    request<Record<string, unknown>>("/companion/sync", {
      method: "POST",
      body: JSON.stringify({ device_id: deviceId, token, clipboard, location }),
    }),
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
export type KnowledgeHit = {
  id: number;
  domain: string;
  title: string;
  content: string;
  source: string;
  score?: number;
  tags?: string[];
};
export type LearningJob = {
  id: number;
  domain: string;
  goal: string;
  status: string;
  resources: Array<Record<string, unknown>>;
  expected_terms: string[];
  result: Record<string, unknown>;
  created_at: number;
  updated_at: number;
  completed_at?: number | null;
};
export type SecurityStatus = {
  emergency_stop: boolean;
  health: Record<string, unknown>;
};
export type SecurityAuditItem = {
  timestamp: number;
  ip: string;
  endpoint: string;
  method: string;
  status: number;
};
export type MCPTool = {
  name?: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
  _server?: string;
};
export type PluginRegistryStatus = {
  registry_available: boolean;
  plugins: Array<Record<string, unknown>>;
  message: string;
  connectors: Array<{ name: string; health: string; capabilities: string[] }>;
  capabilities: Array<Record<string, unknown>>;
};
export type CognitionStatus = {
  identity?: { name?: string; role?: string; truthfulness_rules?: string[]; conversation_style?: string[] };
  loop?: string[];
  last_monitor?: Record<string, unknown>;
  last_context_summary?: {
    request?: string;
    source?: string;
    memory_hits?: number;
    knowledge_hits?: number;
    perceived_inputs?: number;
    voice_language?: string;
  };
  memory_count?: number;
  knowledge?: { domains?: number; entries?: number };
};
export type OrchestrationTask = {
  id: string;
  worker_application: string;
  status: string;
  description: string;
  workspace_id?: string;
  waiting_reason?: string;
  failure?: string;
};
export type OrchestrationProject = {
  project_id: string;
  name: string;
  goal: string;
  status: string;
  root_path: string;
  tasks: OrchestrationTask[];
  target_workers: string[];
  conflict_report?: Record<string, unknown> | null;
};
export type NetworkNode = { id: string; label: string; type?: string };
export type NetworkEdge = { source: string; target: string };

export function wsEventsUrl(): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/ws/events`;
}
