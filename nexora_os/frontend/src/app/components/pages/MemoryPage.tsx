import React, { useEffect, useState } from "react";
import { Database, Search, Sparkles, Filter, Layers, Network } from "lucide-react";
import { nexoraApi, NetworkNode } from "../../../api/client";
import { useNexora } from "../../../context/NexoraContext";

const MEMORY_CATEGORIES = [
  { id: "all", label: "All Types" },
  { id: "preference", label: "User Preferences" },
  { id: "failure", label: "Useful Failures" },
  { id: "workflow", label: "Workflows" },
  { id: "episodic", label: "Episodic" },
  { id: "semantic", label: "Semantic" },
  { id: "general", label: "General" },
];

export function MemoryPage() {
  const { memoryItems, memoryCount, refreshMemory } = useNexora();
  const [query, setQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [network, setNetwork] = useState<NetworkNode[]>([]);
  const [reflection, setReflection] = useState("");
  const [typedMemories, setTypedMemories] = useState<Array<{ id: number; content: string; summary: string; memory_type: string; tags: string[] }>>([]);

  useEffect(() => {
    nexoraApi.memoryNetwork().then((n) => setNetwork(n.nodes || [])).catch(() => setNetwork([]));
  }, [memoryCount]);

  useEffect(() => {
    if (selectedCategory !== "all") {
      nexoraApi.memoryByType(selectedCategory, 20).then((res) => setTypedMemories(res.items || [])).catch(() => setTypedMemories([]));
    }
  }, [selectedCategory]);

  const displayItems = selectedCategory === "all" ? memoryItems : typedMemories;

  return (
    <div className="flex-1 flex flex-col p-6 space-y-6 overflow-y-auto no-scrollbar font-mono text-xs select-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-base font-bold text-slate-100 uppercase tracking-widest flex items-center gap-2">
            <Database className="w-4 h-4 text-cyan-400" />
            Cognitive Memory Engine — {memoryCount} Chunks
          </h1>
          <p className="text-[11px] text-slate-500 font-sans mt-0.5">
            Vectorized episodic, semantic, workflow, and user preference storage with automated category classification
          </p>
        </div>

        <button
          onClick={() => nexoraApi.memoryReflect(query).then((res) => setReflection(res.reflection))}
          className="px-3 py-1.5 rounded-lg bg-cyan-950/60 border border-cyan-500/40 text-cyan-300 hover:bg-cyan-900/60 transition-colors flex items-center gap-1.5"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Run Memory Reflection</span>
        </button>
      </div>

      {/* Category Tabs & Search Bar */}
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-4">
          {/* Search Input */}
          <div className="flex gap-2 flex-1 max-w-md">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && refreshMemory(query)}
              placeholder="Search memories by context or keyword..."
              className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-500/50"
            />
            <button
              onClick={() => refreshMemory(query)}
              className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200"
            >
              <Search className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Category Pills */}
        <div className="flex flex-wrap gap-2 pt-1 border-t border-slate-800/60">
          {MEMORY_CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-1 rounded-md text-xs transition-colors ${
                selectedCategory === cat.id
                  ? "bg-cyan-950 border border-cyan-500/40 text-cyan-300 font-medium"
                  : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Reflection Summary Banner if generated */}
      {reflection && (
        <div className="p-3 rounded-lg bg-cyan-950/40 border-l-4 border-cyan-400 text-cyan-200 text-xs">
          <span className="font-semibold block text-cyan-400 mb-1">Reflection Summary:</span>
          {reflection}
        </div>
      )}

      {/* Main Memory List & Node Graph */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Memory Items List (Left 2 Cols) */}
        <div className="lg:col-span-2 p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-3">
          <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
            Stored Memories Timeline ({displayItems.length})
          </span>

          <div className="space-y-3 max-h-[500px] overflow-y-auto no-scrollbar">
            {displayItems.map((item, idx) => (
              <div key={idx} className="p-3.5 rounded-lg bg-slate-900/90 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-300 font-semibold text-xs truncate max-w-md">
                    {item.summary || item.content?.slice(0, 80)}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-cyan-400 uppercase font-mono border border-slate-700">
                    {item.memory_type || "semantic"}
                  </span>
                </div>
                <p className="text-xs text-slate-400 whitespace-pre-wrap leading-relaxed">
                  {item.content || item.summary}
                </p>
              </div>
            ))}

            {displayItems.length === 0 && (
              <div className="text-slate-500 text-center py-8">
                No memories found in this category.
              </div>
            )}
          </div>
        </div>

        {/* Memory Network Nodes (Right 1 Col) */}
        <div className="p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-3">
          <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2 border-b border-slate-800 pb-2">
            <Network className="w-4 h-4 text-cyan-400" />
            Memory Network Nodes ({network.length})
          </span>

          <div className="space-y-2 max-h-[500px] overflow-y-auto no-scrollbar">
            {network.map((node) => (
              <div key={node.id} className="p-2.5 rounded bg-slate-900/80 border border-slate-800 text-[11px] space-y-1">
                <div className="flex justify-between text-slate-400">
                  <span>Node #{node.id}</span>
                  <span className="text-cyan-400 uppercase">{node.type}</span>
                </div>
                <div className="text-slate-300 truncate">{node.label}</div>
              </div>
            ))}

            {network.length === 0 && (
              <div className="text-slate-500 text-center py-8">No network nodes available.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
