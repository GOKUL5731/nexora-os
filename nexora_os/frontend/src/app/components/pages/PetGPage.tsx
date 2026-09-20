import React, { useMemo, useState } from "react";
import { Bot, HeartHandshake, MessageSquareText, Radar, Rotate3D, Sparkles } from "lucide-react";
import { PetGStage } from "../3d/PetGStage";
import { useNexora } from "../../../context/NexoraContext";

const moods = [
  { id: "idle", label: "Calm", note: "Companion mode" },
  { id: "focus", label: "Focus", note: "Task watcher" },
  { id: "happy", label: "Happy", note: "Assistive mode" },
] as const;

export function PetGPage() {
  const { connected, busy, lastMessage, events, memoryCount, sendCommand } = useNexora();
  const [mood, setMood] = useState<(typeof moods)[number]["id"]>("idle");
  const recentEvents = useMemo(() => events.slice(-4).reverse(), [events]);

  async function askPetG() {
    await sendCommand("summarize your current system state and next best action", { source: "pet_g" });
  }

  return (
    <div className="g-page pet-page">
      <section className="pet-hero">
        <div className="pet-copy">
          <span className="g-eyebrow">PET G / COMPANION MODEL</span>
          <h1>G has a face now.</h1>
          <p>
            A live in-app 3D companion for the local cognitive OS. It reflects task state, keeps the
            command surface close, and stays connected to the same backend event stream as the rest of NEXORA.
          </p>
          <div className="pet-actions">
            <button type="button" onClick={askPetG} disabled={!connected || busy} className="g-primary">
              <MessageSquareText size={17} />
              Ask Pet G
            </button>
            <button type="button" onClick={() => setMood("happy")} className="g-secondary">
              <HeartHandshake size={17} />
              Cheer
            </button>
          </div>
        </div>

        <div className="pet-model-wrap">
          <PetGStage mood={busy ? "focus" : mood} />
          <div className="pet-status-strip" role="status">
            <span className={connected ? "is-online" : "is-offline"} />
            {connected ? (busy ? "Thinking with you" : "Linked to local runtime") : "Runtime offline"}
          </div>
        </div>
      </section>

      <section className="pet-control-grid" aria-label="Pet G controls and status">
        <div className="g-panel">
          <div className="g-panel-title">
            <Sparkles size={16} />
            Mood
          </div>
          <div className="pet-mood-list">
            {moods.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={mood === item.id}
                onClick={() => setMood(item.id)}
                className={mood === item.id ? "is-selected" : ""}
              >
                <strong>{item.label}</strong>
                <span>{item.note}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="g-panel">
          <div className="g-panel-title">
            <Radar size={16} />
            Runtime Feed
          </div>
          <div className="pet-feed">
            {recentEvents.length ? (
              recentEvents.map((event) => (
                <div key={event.sequence}>
                  <span>#{event.sequence}</span>
                  <p>{event.topic}</p>
                </div>
              ))
            ) : (
              <p className="muted">Waiting for backend events.</p>
            )}
          </div>
        </div>

        <div className="g-panel">
          <div className="g-panel-title">
            <Bot size={16} />
            Companion Memory
          </div>
          <dl className="pet-stats">
            <div>
              <dt>Stored memories</dt>
              <dd>{connected ? memoryCount : "--"}</dd>
            </div>
            <div>
              <dt>Last response</dt>
              <dd>{lastMessage}</dd>
            </div>
          </dl>
        </div>

        <div className="g-panel">
          <div className="g-panel-title">
            <Rotate3D size={16} />
            Model Notes
          </div>
          <p className="muted">
            This is a procedural Three.js model built directly into the frontend. It can later be swapped
            for a generated GLB after an explicit paid asset-generation confirmation.
          </p>
        </div>
      </section>
    </div>
  );
}
