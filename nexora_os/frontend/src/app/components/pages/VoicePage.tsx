import React, { useEffect, useState } from "react";
import { Mic, Volume2 } from "lucide-react";
import { nexoraApi } from "../../../api/client";
import { useNexora } from "../../../context/NexoraContext";
import { CommandBar } from "../CommandBar";

export function VoicePage() {
  const { voiceState, lastMessage, startVoice, speak, busy, connected } = useNexora();
  const [voiceStatus, setVoiceStatus] = useState<Record<string, unknown>>({});

  useEffect(() => {
    nexoraApi.voiceStatus().then(setVoiceStatus).catch((error) => setVoiceStatus({ error: String(error) }));
  }, []);

  return (
    <div className="flex-1 flex flex-col p-8 gap-6 overflow-auto">
      <h2 className="text-xl font-['Rajdhani'] text-cyan-400 tracking-widest uppercase">Voice Engine</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border border-cyan-500/20 rounded-xl p-6 bg-black/40">
          <div className="flex items-center gap-3 mb-4">
            <Mic className="w-6 h-6 text-cyan-400" />
            <span className="font-mono text-cyan-300 uppercase text-sm">Status: {voiceState}</span>
          </div>
          <p className="text-sm text-cyan-600/90 font-mono mb-4">{lastMessage}</p>
          <button
            disabled={!connected || busy}
            onClick={startVoice}
            className="w-full py-3 rounded-lg border border-cyan-500/40 text-cyan-200 hover:bg-cyan-950/30 disabled:opacity-40 font-['Rajdhani'] tracking-wider"
          >
            Listen & Process
          </button>
        </div>
        <div className="border border-cyan-500/20 rounded-xl p-6 bg-black/40">
          <Volume2 className="w-6 h-6 text-cyan-400 mb-4" />
          <div className="text-xs text-cyan-600 mb-4 space-y-1 font-mono">
            <p>STT available: {String(voiceStatus.stt_available ?? "unknown")}</p>
            <p>TTS available: {String(voiceStatus.tts_available ?? "unknown")}</p>
            <p>Languages: {Array.isArray(voiceStatus.languages) ? voiceStatus.languages.join(" / ") : "unknown"}</p>
          </div>
          <button
            disabled={!connected}
            onClick={() => speak("NEXORA voice systems operational.")}
            className="w-full py-2 rounded border border-cyan-900/50 text-cyan-500 text-sm hover:text-cyan-300"
          >
            Test TTS
          </button>
        </div>
      </div>
      <CommandBar />
    </div>
  );
}
