import React, { useCallback, useEffect, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  Connection,
  Node,
  Edge,
  Panel,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Play, Save, Sparkles, Plus, Trash2 } from "lucide-react";
import { nexoraApi, GraphSpec } from "../../../api/client";
import { cn } from "../../utils";

const DEFAULT_NODES: Node[] = [
  {
    id: "trigger",
    type: "default",
    position: { x: 80, y: 120 },
    data: { label: "Trigger", nodeType: "trigger" },
    style: { background: "#0a1628", border: "1px solid #06b6d4", color: "#a5f3fc", minWidth: 140 },
  },
];

const NODE_PALETTE = [
  "trigger", "scheduler", "voice_input", "llm", "memory_save", "browser",
  "ocr", "camera", "file_save", "agent_spawn", "api_call", "workflow_trigger",
  "condition", "loop", "wait", "notify",
];

function specToFlow(spec: GraphSpec): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = (spec.graph?.nodes || []).map((n) => ({
    id: n.id,
    type: "default",
    position: n.position || { x: 0, y: 0 },
    data: { label: n.type, nodeType: n.type, ...n.data },
    style: { background: "#0a1628", border: "1px solid #06b6d4", color: "#e0f2fe", minWidth: 150 },
  }));
  const edges: Edge[] = (spec.graph?.edges || []).map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: true,
    style: { stroke: "#06b6d4" },
  }));
  return { nodes: nodes.length ? nodes : DEFAULT_NODES, edges };
}

function flowToSpec(name: string, description: string, nodes: Node[], edges: Edge[]): GraphSpec {
  return {
    name,
    description,
    graph: {
      nodes: nodes.map((n) => ({
        id: n.id,
        type: (n.data as { nodeType?: string }).nodeType || "log",
        data: Object.fromEntries(
          Object.entries(n.data as Record<string, unknown>).filter(([k]) => k !== "label" && k !== "nodeType"),
        ),
        position: n.position,
      })),
      edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
    },
  };
}

export function WorkflowStudio() {
  const [name, setName] = useState("my_workflow");
  const [description, setDescription] = useState("");
  const [nodes, setNodes, onNodesChange] = useNodesState(DEFAULT_NODES);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [trace, setTrace] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [graphs, setGraphs] = useState<Array<{ name: string }>>([]);

  const refreshList = useCallback(async () => {
    try {
      const res = await nexoraApi.listGraphs();
      setGraphs(res.graphs || []);
    } catch {
      setGraphs([]);
    }
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  const onConnect = useCallback(
    (conn: Connection) => setEdges((eds) => addEdge({ ...conn, animated: true, style: { stroke: "#06b6d4" } }, eds)),
    [setEdges],
  );

  const addNode = (type: string) => {
    const id = `${type}_${Date.now().toString(36).slice(-4)}`;
    setNodes((nds) => [
      ...nds,
      {
        id,
        type: "default",
        position: { x: 100 + nds.length * 40, y: 80 + nds.length * 30 },
        data: { label: type, nodeType: type },
        style: { background: "#0a1628", border: "1px solid #0891b2", color: "#cffafe", minWidth: 150 },
      },
    ]);
  };

  const save = async () => {
    setBusy(true);
    try {
      const spec = flowToSpec(name, description, nodes, edges);
      await nexoraApi.saveGraph(spec);
      setTrace(`Saved workflow '${name}'`);
      await refreshList();
    } catch (e) {
      setTrace(String(e));
    } finally {
      setBusy(false);
    }
  };

  const run = async () => {
    setBusy(true);
    try {
      await save();
      const result = await nexoraApi.runGraph(name);
      setTrace(JSON.stringify(result, null, 2));
      const tr = await nexoraApi.workflowTrace(name);
      setTrace((prev) => prev + "\n\nTRACE:\n" + JSON.stringify(tr.trace?.slice(-8), null, 2));
    } catch (e) {
      setTrace(String(e));
    } finally {
      setBusy(false);
    }
  };

  const generate = async () => {
    if (!description.trim()) return;
    setBusy(true);
    try {
      const res = await nexoraApi.generateWorkflow(description);
      if (res.spec) {
        setName(res.spec.name);
        const { nodes: n, edges: e } = specToFlow(res.spec);
        setNodes(n);
        setEdges(e);
        setTrace(`Generated ${res.spec.graph.nodes.length} nodes`);
        await nexoraApi.saveGraph(res.spec);
        await refreshList();
      } else {
        setTrace(JSON.stringify(res));
      }
    } catch (e) {
      setTrace(String(e));
    } finally {
      setBusy(false);
    }
  };

  const loadGraph = async (gname: string) => {
    try {
      const spec = await nexoraApi.getGraph(gname);
      if (spec && !("error" in spec)) {
        setName(spec.name);
        setDescription(spec.description || "");
        const { nodes: n, edges: e } = specToFlow(spec);
        setNodes(n);
        setEdges(e);
      }
    } catch (e) {
      setTrace(String(e));
    }
  };

  return (
    <div className="flex-1 flex h-full min-h-0">
      <div className="w-52 border-r border-cyan-900/40 bg-black/50 p-3 flex flex-col gap-2 overflow-y-auto">
        <p className="text-[10px] text-cyan-600 font-mono uppercase tracking-widest mb-1">Nodes</p>
        {NODE_PALETTE.map((t) => (
          <button
            key={t}
            onClick={() => addNode(t)}
            className="text-left text-xs font-mono text-cyan-400 hover:bg-cyan-950/40 px-2 py-1.5 rounded border border-transparent hover:border-cyan-800"
          >
            + {t}
          </button>
        ))}
        <hr className="border-cyan-900/40 my-2" />
        <p className="text-[10px] text-cyan-600 font-mono uppercase">Saved</p>
        {graphs.map((g) => (
          <button
            key={g.name}
            onClick={() => loadGraph(g.name)}
            className="text-left text-xs text-cyan-500 hover:text-cyan-200 truncate"
          >
            {g.name}
          </button>
        ))}
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex flex-wrap items-center gap-2 p-3 border-b border-cyan-900/30 bg-black/40">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="bg-black/60 border border-cyan-800/50 rounded px-2 py-1 text-sm text-cyan-100 font-mono w-40"
            placeholder="workflow name"
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="flex-1 min-w-[200px] bg-black/60 border border-cyan-800/50 rounded px-2 py-1 text-sm text-cyan-200 font-mono"
            placeholder="Describe workflow for AI generator…"
          />
          <button disabled={busy} onClick={generate} className="flex items-center gap-1 px-3 py-1.5 rounded border border-cyan-500/40 text-cyan-300 text-xs hover:bg-cyan-950/30 disabled:opacity-40">
            <Sparkles className="w-3 h-3" /> Generate
          </button>
          <button disabled={busy} onClick={save} className="flex items-center gap-1 px-3 py-1.5 rounded border border-cyan-500/40 text-cyan-300 text-xs hover:bg-cyan-950/30 disabled:opacity-40">
            <Save className="w-3 h-3" /> Save
          </button>
          <button disabled={busy} onClick={run} className="flex items-center gap-1 px-3 py-1.5 rounded bg-cyan-900/40 border border-cyan-400/50 text-cyan-100 text-xs hover:bg-cyan-800/30 disabled:opacity-40">
            <Play className="w-3 h-3" /> Run
          </button>
        </div>

        <div className="flex-1 min-h-[400px]">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            fitView
            className="bg-[#010308]"
          >
            <Background color="#0e7490" gap={20} />
            <Controls />
            <MiniMap nodeColor="#06b6d4" maskColor="rgb(0,0,0,0.8)" />
            <Panel position="top-right" className="text-[10px] text-cyan-600 font-mono">
              {nodes.length} nodes · {edges.length} edges
            </Panel>
          </ReactFlow>
        </div>

        {trace && (
          <pre className="max-h-32 overflow-auto text-[10px] font-mono text-cyan-600/90 p-3 border-t border-cyan-900/30 bg-black/60">
            {trace}
          </pre>
        )}
      </div>
    </div>
  );
}
