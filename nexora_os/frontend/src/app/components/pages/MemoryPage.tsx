import React, { useEffect, useState } from "react";
import { Database, Search } from "lucide-react";
import { nexoraApi, NetworkNode } from "../../../api/client";
import { useNexora } from "../../../context/NexoraContext";
import { CommandBar } from "../CommandBar";

export function MemoryPage() {
  const { memoryItems, memoryCount, refreshMemory } = useNexora();
  const [query, setQuery] = useState("");
  const [network, setNetwork] = useState<NetworkNode[]>([]);
  const [reflection, setReflection] = useState("");

  useEffect(() => {
    nexoraApi.memoryNetwork().then((n) => setNetwork(n.nodes || [])).catch(() => setNetwork([]));
  }, [memoryCount]);

  return (
    <div className="flex-1 flex flex-col p-8 gap-6 overflow-auto">
      <h2 className="text-xl font-['Rajdhani'] text-cyan-400 tracking-widest uppercase">
        Memory · {memoryCount} interactions
      </h2>
      <div className="flex gap-2 max-w-md">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search memory…"
          className="flex-1 bg-black/50 border border-cyan-900/40 rounded-lg px-3 py-2 text-sm text-cyan-100 font-mono outline-none"
        />
        <button
          onClick={() => refreshMemory(query)}
          className="p-2 rounded-lg border border-cyan-500/40 text-cyan-400"
        >
          <Search className="w-5 h-5" />
        </button>
        <button
          onClick={() => nexoraApi.memoryReflect(query).then((result) => setReflection(result.reflection))}
          className="px-3 rounded-lg border border-cyan-500/40 text-cyan-400 text-xs"
        >
          Reflect
        </button>
      </div>
      {reflection && <p className="text-xs font-mono text-cyan-500 border-l-2 border-cyan-600 pl-3">{reflection}</p>}
      {network.length > 0 && (
        <div className="flex flex-wrap gap-2 p-4 border border-cyan-900/30 rounded-xl bg-black/30 min-h-[120px]">
          {network.map((n) => (
            <div
              key={n.id}
              className="px-2 py-1 rounded-full border border-cyan-700/40 text-[10px] font-mono text-cyan-500"
              title={n.label}
            >
              {n.label}
            </div>
          ))}
        </div>
      )}
      <div className="flex flex-col gap-2">
        {memoryItems.map((m, i) => (
          <div key={i} className="p-3 rounded-lg border border-cyan-900/30 bg-cyan-950/10 flex gap-2">
            <Database className="w-4 h-4 text-cyan-600 shrink-0 mt-0.5" />
            <p className="text-xs font-mono text-cyan-500/90">{m.summary ?? m.content ?? JSON.stringify(m)}</p>
          </div>
        ))}
      </div>
      <CommandBar />
    </div>
  );
}
