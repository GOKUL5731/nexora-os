import React, { useEffect, useState } from "react";
import { FlaskConical } from "lucide-react";
import { nexoraApi } from "../../../api/client";
import { useNexora } from "../../../context/NexoraContext";

export function LabPage() {
  const { status, events } = useNexora();
  const [settings, setSettings] = useState<Record<string, unknown>>({});

  useEffect(() => {
    nexoraApi.settings().then(setSettings).catch((error) => setSettings({ error: String(error) }));
  }, []);

  const llm = (settings.llm ?? {}) as Record<string, unknown>;

  return (
    <div className="flex-1 p-8 overflow-auto">
      <h2 className="text-xl font-['Rajdhani'] text-cyan-400 tracking-widest uppercase flex gap-2 items-center">
        <FlaskConical className="w-5 h-5" /> AI Lab
      </h2>
      <p className="mt-2 text-xs font-mono text-cyan-700">
        Recovery Mode: agent generation is disabled. This page shows only live model and runtime diagnostics.
      </p>
      <div className="mt-6 grid md:grid-cols-3 gap-3">
        <div className="p-4 rounded-xl border border-cyan-900/40 bg-black/40">
          <p className="text-[10px] font-mono text-cyan-700 uppercase">LLM Ready</p>
          <p className={status?.llm_ready ? "text-emerald-400" : "text-amber-400"}>
            {status?.llm_ready ? "READY" : "NOT READY"}
          </p>
        </div>
        <div className="p-4 rounded-xl border border-cyan-900/40 bg-black/40">
          <p className="text-[10px] font-mono text-cyan-700 uppercase">Ollama Host</p>
          <p className="text-cyan-300 break-all">{String(llm.host ?? "unknown")}</p>
        </div>
        <div className="p-4 rounded-xl border border-cyan-900/40 bg-black/40">
          <p className="text-[10px] font-mono text-cyan-700 uppercase">Model</p>
          <p className="text-cyan-300">{String(llm.model || "no local model detected")}</p>
        </div>
      </div>
      <div className="mt-6 p-4 rounded-xl border border-cyan-900/40 bg-black/40">
        <p className="text-[10px] font-mono text-cyan-700 uppercase mb-3">Recent AI / Runtime Events</p>
        {events.slice(-20).reverse().map((event) => (
          <div key={event.sequence} className="text-[10px] font-mono text-cyan-600 truncate">
            {event.sequence} {event.topic}
          </div>
        ))}
      </div>
    </div>
  );
}
