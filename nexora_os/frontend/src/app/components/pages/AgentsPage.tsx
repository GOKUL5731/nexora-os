import React, { useState } from "react";
import { Cpu, Play } from "lucide-react";
import { nexoraApi } from "../../../api/client";
import { useNexora } from "../../../context/NexoraContext";

type RuntimeAgent = {
  name: string;
  status: string;
  queued?: number;
  completed?: number;
  failed?: number;
};

export function AgentsPage() {
  const { agents, connected } = useNexora();
  const [result, setResult] = useState("");

  const run = async (name: string) => {
    const response = await nexoraApi.agentTask(name, { input: `Health check requested for ${name}` });
    setResult(JSON.stringify(response, null, 2));
  };

  return (
    <div className="flex-1 p-8 overflow-auto">
      <h2 className="text-xl font-['Rajdhani'] text-cyan-400 tracking-widest uppercase mb-6">Agent Runtime</h2>
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
        {(agents.runtime as RuntimeAgent[]).map((agent) => (
          <div key={agent.name} className="p-4 rounded-xl border border-cyan-900/40 bg-black/40">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2"><Cpu className="w-4 h-4 text-cyan-500" /><span className="text-cyan-100">{agent.name}</span></div>
              <span className="text-[10px] font-mono text-cyan-500 uppercase">{agent.status}</span>
            </div>
            <div className="grid grid-cols-3 gap-2 mt-4 text-[10px] font-mono text-cyan-700">
              <span>Queue {agent.queued ?? 0}</span>
              <span>Done {agent.completed ?? 0}</span>
              <span>Failed {agent.failed ?? 0}</span>
            </div>
            <button disabled={!connected} onClick={() => run(agent.name)} className="mt-4 flex items-center gap-1 text-xs text-cyan-400 disabled:opacity-40">
              <Play className="w-3 h-3" /> Queue health task
            </button>
          </div>
        ))}
      </div>
      {result && <pre className="mt-6 max-h-52 overflow-auto p-4 border border-cyan-900/40 rounded-xl text-[10px] text-cyan-600 bg-black/50">{result}</pre>}
    </div>
  );
}
