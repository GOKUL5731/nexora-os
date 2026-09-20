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
import { Boxes, Play, Save, Sparkles } from "lucide-react";
import { nexoraApi, GraphSpec } from "../../../api/client";
import { cn } from "../../utils";

const DEFAULT_NODES: Node[] = [
  {
    id: "trigger",
    type: "default",
    position: { x: 80, y: 120 },
    data: { label: "Trigger", nodeType: "trigger" },
    style: { background: "#111827", border: "1px solid rgba(148,163,184,.28)", color: "#e5e7eb", minWidth: 140, borderRadius: 14 },
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
    style: { background: "#111827", border: "1px solid rgba(148,163,184,.28)", color: "#e5e7eb", minWidth: 150, borderRadius: 14 },
  }));
  const edges: Edge[] = (spec.graph?.edges || []).map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: true,
    style: { stroke: "#38bdf8" },
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
    (conn: Connection) => setEdges((eds) => addEdge({ ...conn, animated: true, style: { stroke: "#38bdf8" } }, eds)),
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
        style: { background: "#111827", border: "1px solid rgba(148,163,184,.28)", color: "#e5e7eb", minWidth: 150, borderRadius: 14 },
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
    <div className="g-workflow-shell">
      <aside className="g-workflow-sidebar">
        <div className="g-section-heading">
          <span>Node palette</span>
          <small>{NODE_PALETTE.length}</small>
        </div>
        {NODE_PALETTE.map((t) => (
          <button
            key={t}
            onClick={() => addNode(t)}
            className="g-node-chip"
          >
            <Boxes className="h-3.5 w-3.5" />
            {t}
          </button>
        ))}
        <div className="g-sidebar-divider" />
        <div className="g-section-heading">
          <span>Saved flows</span>
          <small>{graphs.length}</small>
        </div>
        {graphs.map((g) => (
          <button
            key={g.name}
            onClick={() => loadGraph(g.name)}
            className="g-saved-flow"
          >
            {g.name}
          </button>
        ))}
      </aside>

      <div className="g-workflow-main">
        <div className="g-workflow-toolbar">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="g-workflow-name"
            placeholder="workflow name"
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="g-workflow-description"
            placeholder="Describe workflow for AI generator…"
          />
          <button disabled={busy} onClick={generate} className="g-secondary-action">
            <Sparkles className="w-3 h-3" /> Generate
          </button>
          <button disabled={busy} onClick={save} className="g-secondary-action">
            <Save className="w-3 h-3" /> Save
          </button>
          <button disabled={busy} onClick={run} className="g-primary-action">
            <Play className="w-3 h-3" /> Run
          </button>
        </div>

        <div className="g-flow-canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            fitView
            className="g-react-flow"
          >
            <Background color="#334155" gap={24} />
            <Controls />
            <MiniMap nodeColor="#38bdf8" maskColor="rgb(2,6,23,0.82)" />
            <Panel position="top-right" className="g-flow-count">
              {nodes.length} nodes · {edges.length} edges
            </Panel>
          </ReactFlow>
        </div>

        {trace && (
          <pre className="g-workflow-trace">
            {trace}
          </pre>
        )}
      </div>
    </div>
  );
}
