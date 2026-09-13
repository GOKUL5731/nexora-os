import React, { useEffect, useState } from "react";
import { Mic, Volume2, Languages, Radio, Activity, Play, CheckCircle2 } from "lucide-react";
import { useNexora } from "../../../context/NexoraContext";
import { nexoraApi } from "../../../api/client";

export function VoicePage() {
  const { voiceState, startVoice, speak, lastMessage, connected } = useNexora();
  const [ttsInput, setTtsInput] = useState("Hello! Jarvis voice system is online.");
  const [selectedLang, setSelectedLang] = useState("ta-en");
  const [livekit, setLivekit] = useState<Record<string, unknown> | null>(null);

  const isListening = voiceState === "listening";
  const isSpeaking = voiceState === "speaking";

  useEffect(() => {
    nexoraApi.livekitStatus().then(setLivekit).catch(() => setLivekit(null));
  }, []);

  const handleSpeak = async () => {
    if (!ttsInput.trim()) return;
    await speak(ttsInput);
  };

  return (
    <div className="flex-1 flex flex-col p-6 space-y-6 overflow-y-auto no-scrollbar font-mono text-xs select-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-base font-bold text-slate-100 uppercase tracking-widest flex items-center gap-2">
            <Mic className="w-4 h-4 text-cyan-400" />
            Voice AI Pipeline & Multilingual Speech
          </h1>
          <p className="text-[11px] text-slate-500 font-sans mt-0.5">
            Voice Activity Detection (VAD), Tamil / Tanglish / English speech recognition, and streaming TTS
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className={`px-2.5 py-1 rounded text-[11px] font-mono border ${
            isListening ? "bg-rose-950 border-rose-800 text-rose-400 animate-pulse" :
            isSpeaking ? "bg-cyan-950 border-cyan-800 text-cyan-400 animate-pulse" :
            "bg-slate-900 border-slate-800 text-slate-400"
          }`}>
            Status: {voiceState.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 1 Col: Voice Controls & Microphone Visualizer */}
        <div className="p-5 rounded-xl bg-[#090d19] border border-slate-800 space-y-5">
          <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
            Microphone & VAD Meter
          </span>

          {/* Animated Mic Status Visualizer */}
          <div className="flex flex-col items-center justify-center p-6 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
            <button
              onClick={startVoice}
              disabled={!connected}
              className={`w-20 h-20 rounded-full border flex items-center justify-center transition-all ${
                isListening
                  ? "bg-rose-500/20 border-rose-500 text-rose-400 shadow-[0_0_30px_rgba(244,63,94,0.4)] animate-pulse"
                  : "bg-cyan-500/10 border-cyan-500/30 text-cyan-400 hover:scale-105"
              }`}
            >
              <Mic className="w-8 h-8" />
            </button>

            <span className="text-xs text-slate-300 font-semibold">
              {isListening ? "Listening for speech…" : "Click Microphone to Listen"}
            </span>

            <div className="flex items-center gap-2 text-[10px] text-slate-500">
              <Radio className="w-3 h-3 text-cyan-400" />
              <span>VAD RMS Threshold: 500</span>
            </div>
          </div>

          {/* Supported Languages Selector */}
          <div className="space-y-2">
            <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Language Model Engine</span>
            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => setSelectedLang("ta-en")}
                className={`p-2 rounded border text-center text-xs ${
                  selectedLang === "ta-en"
                    ? "bg-cyan-950 border-cyan-500/40 text-cyan-300 font-semibold"
                    : "bg-slate-900 border-slate-800 text-slate-400"
                }`}
              >
                Tanglish (ta-en)
              </button>
              <button
                onClick={() => setSelectedLang("ta")}
                className={`p-2 rounded border text-center text-xs ${
                  selectedLang === "ta"
                    ? "bg-cyan-950 border-cyan-500/40 text-cyan-300 font-semibold"
                    : "bg-slate-900 border-slate-800 text-slate-400"
                }`}
              >
                Tamil (ta)
              </button>
              <button
                onClick={() => setSelectedLang("en")}
                className={`p-2 rounded border text-center text-xs ${
                  selectedLang === "en"
                    ? "bg-cyan-950 border-cyan-500/40 text-cyan-300 font-semibold"
                    : "bg-slate-900 border-slate-800 text-slate-400"
                }`}
              >
                English (en)
              </button>
            </div>
          </div>
        </div>

        {/* Right 2 Cols: Speech Synthesis & Transcription Stream */}
        <div className="lg:col-span-2 space-y-6">
          <div className="p-4 rounded-xl bg-[#090d19] border border-slate-800 flex items-center justify-between gap-4">
            <div>
              <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block">LiveKit Realtime Transport</span>
              <p className="text-[11px] text-slate-500 font-sans mt-1">
                Realtime voice/video transport with Ollama as the reasoning provider.
              </p>
            </div>
            <span className={`px-2.5 py-1 rounded border text-[11px] ${livekit?.configured ? "border-emerald-800 bg-emerald-950 text-emerald-400" : "border-amber-800 bg-amber-950 text-amber-400"}`}>
              {livekit ? (livekit.configured ? "CONFIGURED" : "NOT CONFIGURED") : "CHECKING"}
            </span>
          </div>

          {/* TTS Synthesizer Card */}
          <div className="p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-3">
            <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2 border-b border-slate-800 pb-2">
              <Volume2 className="w-4 h-4 text-cyan-400" />
              Text-to-Speech (TTS) Synthesizer
            </span>

            <div className="flex gap-2">
              <input
                type="text"
                value={ttsInput}
                onChange={(e) => setTtsInput(e.target.value)}
                placeholder="Enter text to speak..."
                className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-500/50"
              />
              <button
                onClick={handleSpeak}
                disabled={!connected || !ttsInput.trim()}
                className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium disabled:opacity-40 transition-colors flex items-center gap-1.5"
              >
                <Play className="w-4 h-4" />
                <span>Speak</span>
              </button>
            </div>
          </div>

          {/* Live Transcription Stream */}
          <div className="p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-3">
            <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
              Live Speech Transcript Log
            </span>

            <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 min-h-[160px] text-xs text-slate-200 space-y-2">
              <div className="flex items-center justify-between text-[10px] text-slate-500 border-b border-slate-800 pb-1">
                <span>LAST UTTERANCE</span>
                <span className="text-cyan-400">Detected: {selectedLang}</span>
              </div>
              <p className="text-slate-300 italic font-sans text-sm">"{lastMessage}"</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
