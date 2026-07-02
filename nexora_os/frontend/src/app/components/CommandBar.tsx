import React, { useState } from "react";
import { Mic, Send, Loader2 } from "lucide-react";
import { useNexora } from "../../context/NexoraContext";
import { cn } from "../utils";

export function CommandBar({ className }: { className?: string }) {
  const { sendCommand, startVoice, confirmPending, pendingTaskId, busy, connected } = useNexora();
  const [input, setInput] = useState("");

  const submit = async () => {
    if (!input.trim() || busy) return;
    await sendCommand(input);
    setInput("");
  };

  return (
    <div className={cn("flex flex-col gap-2 w-[calc(100%-1rem)] max-w-2xl mx-auto px-2 md:px-4", className)}>
      {pendingTaskId && (
        <div className="flex gap-2 justify-center text-xs font-mono">
          <button
            onClick={() => confirmPending(true)}
            className="px-3 py-1 rounded border border-cyan-500/50 text-cyan-300 hover:bg-cyan-950/50"
          >
            Confirm
          </button>
          <button
            onClick={() => confirmPending(false)}
            className="px-3 py-1 rounded border border-cyan-900/50 text-cyan-600 hover:bg-black/50"
          >
            Cancel
          </button>
        </div>
      )}
      <div className="flex items-center gap-2 bg-black/60 border border-cyan-500/30 rounded-xl px-3 py-2 backdrop-blur-md shadow-[0_0_20px_rgba(0,255,255,0.08)]">
        <button
          type="button"
          disabled={!connected || busy}
          onClick={startVoice}
          className="p-1.5 md:p-2 rounded-lg text-cyan-400 hover:bg-cyan-950/40 disabled:opacity-40"
          title="Voice input"
        >
          <Mic className="w-5 h-5" />
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder={connected ? "Command NEXORA… (English / Tamil / Tanglish)" : "Start API: python -m nexora_os.backend.api.app"}
          disabled={!connected || busy}
          className="flex-1 min-w-0 bg-transparent text-xs md:text-sm text-cyan-100 placeholder:text-cyan-800 outline-none font-mono"
        />
        <button
          type="button"
          disabled={!connected || busy || !input.trim()}
          onClick={submit}
          className="p-1.5 md:p-2 rounded-lg text-cyan-300 hover:bg-cyan-950/40 disabled:opacity-40"
        >
          {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
        </button>
      </div>
    </div>
  );
}
