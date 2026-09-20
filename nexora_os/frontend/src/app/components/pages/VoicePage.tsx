import React, { useEffect, useState } from "react";
import { Languages, Mic, Play, Radio, Volume2, Waves } from "lucide-react";
import { nexoraApi } from "../../../api/client";
import { useNexora } from "../../../context/NexoraContext";

export function VoicePage() {
  const { voiceState, startVoice, speak, lastMessage, connected } = useNexora();
  const [ttsInput, setTtsInput] = useState("Hello! G voice system is online.");
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
    <div className="g-page">
      <section className="g-page-hero">
        <div>
          <p className="g-eyebrow">Voice AI</p>
          <h1>Speak, listen, and verify realtime transport.</h1>
          <p>VAD, multilingual recognition, TTS, and LiveKit transport status in one calm control room.</p>
        </div>
        <span className={`g-live-pill ${isListening || isSpeaking ? "g-status-good" : "g-status-warn"}`}>
          <Radio className="h-3.5 w-3.5" />
          {voiceState.toUpperCase()}
        </span>
      </section>

      <section className="g-voice-layout">
        <div className="g-panel g-voice-control">
          <div className="g-section-heading">
            <span>Microphone</span>
            <small>VAD threshold 500</small>
          </div>
          <button
            onClick={startVoice}
            disabled={!connected}
            className={`g-mic-button ${isListening ? "listening" : ""}`}
            aria-label="Start voice listening"
          >
            <Mic className="h-9 w-9" />
          </button>
          <h2>{isListening ? "Listening for speech…" : "Ready when runtime is linked"}</h2>
          <p>Voice actions stay disabled until the real backend connection is available.</p>
          <div className="g-language-grid" aria-label="Language model selection">
            {[
              ["ta-en", "Tanglish"],
              ["ta", "Tamil"],
              ["en", "English"],
            ].map(([value, label]) => (
              <button
                key={value}
                onClick={() => setSelectedLang(value)}
                className={selectedLang === value ? "active" : ""}
              >
                <Languages className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="g-voice-stack">
          <div className="g-panel">
            <div className="g-section-heading">
              <span>LiveKit realtime transport</span>
              <small>{livekit ? (livekit.configured ? "configured" : "not configured") : "checking"}</small>
            </div>
            <p className="g-muted-copy">
              Realtime transport is separated from the LLM provider decision. Ollama remains the local reasoning path.
            </p>
          </div>

          <div className="g-panel">
            <div className="g-section-heading">
              <span>Text-to-speech synthesizer</span>
              <small>{isSpeaking ? "speaking" : "idle"}</small>
            </div>
            <div className="g-input-row">
              <input
                type="text"
                value={ttsInput}
                onChange={(event) => setTtsInput(event.target.value)}
                placeholder="Enter text to speak..."
              />
              <button onClick={handleSpeak} disabled={!connected || !ttsInput.trim()} className="g-primary-action">
                <Play className="h-4 w-4" />
                Speak
              </button>
            </div>
          </div>

          <div className="g-panel">
            <div className="g-section-heading">
              <span>Last utterance</span>
              <small>{selectedLang}</small>
            </div>
            <div className="g-transcript-box">
              <Waves className="h-5 w-5" />
              <p>{lastMessage || "No utterance captured yet."}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
