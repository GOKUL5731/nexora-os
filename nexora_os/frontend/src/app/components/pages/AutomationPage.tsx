import React, { useEffect, useState } from "react";
import { Settings2 } from "lucide-react";
import { nexoraApi } from "../../../api/client";

export function AutomationPage() {
  const [actions, setActions] = useState<string[]>([]);
  const [history, setHistory] = useState<Array<Record<string, unknown>>>([]);

  const refresh = async () => {
    const data = await nexoraApi.automation();
    setActions(data.registered_actions);
    setHistory(data.history);
  };

  useEffect(() => { refresh().catch(() => undefined); }, []);

  const run = async (action: string) => {
    await nexoraApi.automationRun(action);
    await refresh();
  };

  return (
    <div className="flex-1 p-8 overflow-auto">
      <h2 className="text-xl font-['Rajdhani'] text-cyan-400 tracking-widest uppercase">Automation</h2>
      <p className="text-xs text-cyan-700 font-mono mt-2">Only registered local actions are executable.</p>
      <div className="grid md:grid-cols-2 gap-3 mt-6">
        {actions.map((action) => (
          <button key={action} onClick={() => run(action)} className="flex items-center gap-2 p-4 rounded-xl border border-cyan-900/40 bg-black/40 text-cyan-300">
            <Settings2 className="w-4 h-4" /> {action}
          </button>
        ))}
      </div>
      <div className="mt-6 space-y-2">
        {history.slice().reverse().map((entry, index) => (
          <pre key={index} className="p-3 rounded border border-cyan-900/30 text-[10px] text-cyan-600 overflow-auto">{JSON.stringify(entry, null, 2)}</pre>
        ))}
      </div>
    </div>
  );
}
