import React, { useEffect, useState } from "react";
import { BrainCircuit, FlaskConical, ServerCog, Sparkles } from "lucide-react";
import { nexoraApi } from "../../../api/client";
import { useNexora } from "../../../context/NexoraContext";

export function LabPage() {
  const { status, events } = useNexora();
  const [settings, setSettings] = useState<Record<string, unknown>>({});

  useEffect(() => {
    nexoraApi.settings().then(setSettings).catch((error) => setSettings({ error: String(error) }));
  }, []);

  const llm = (settings.llm ?? {}) as Record<string, unknown>;
  const labEvents = events.slice(-18).reverse();

  return (
    <div className="g-page">
      <section className="g-page-hero">
        <div>
          <p className="g-eyebrow">AI Lab</p>
          <h1>Model diagnostics without pretending providers exist.</h1>
          <p>Recovery mode stays honest: this lab exposes local model readiness, settings, and runtime event evidence.</p>
        </div>
        <span className={`g-live-pill ${status?.llm_ready ? "g-status-good" : "g-status-warn"}`}>
          <FlaskConical className="h-3.5 w-3.5" />
          {status?.llm_ready ? "LLM ready" : "Model unavailable"}
        </span>
      </section>

      <section className="g-card-grid g-card-grid-three">
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><BrainCircuit className="h-4 w-4" /></span></div>
          <h2>Reasoning state</h2>
          <p>{status?.llm_ready ? "Local reasoning endpoint is reporting ready." : "No ready local model has been reported."}</p>
        </article>
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><ServerCog className="h-4 w-4" /></span></div>
          <h2>Ollama host</h2>
          <p className="break-all">{String(llm.host ?? "unknown")}</p>
        </article>
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><Sparkles className="h-4 w-4" /></span></div>
          <h2>Model</h2>
          <p>{String(llm.model || "no local model detected")}</p>
        </article>
      </section>

      <section className="g-panel">
        <div className="g-section-heading">
          <span>Recent AI / runtime events</span>
          <small>{labEvents.length} visible</small>
        </div>
        {labEvents.length === 0 ? (
          <div className="g-empty-inline">
            <FlaskConical className="h-6 w-6" />
            <p>No runtime events have reached the frontend yet.</p>
          </div>
        ) : (
          <div className="g-event-list">
            {labEvents.map((event) => (
              <div key={event.sequence}>
                <span>#{event.sequence}</span>
                <strong>{event.topic}</strong>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
