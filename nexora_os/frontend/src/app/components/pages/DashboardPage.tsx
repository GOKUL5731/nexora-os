import React, { useState } from "react";
import { ArrowUpRight, Mic, Send, Volume2 } from "lucide-react";
import { useNexora } from "../../../context/NexoraContext";
import "../../../styles/jarvis.css";

export function DashboardPage({ onNavigate }: { onNavigate?: (tab: string) => void }) {
  const { connected, status, brainState, cognitionState, events, modules, voiceState,
    lastMessage, sendCommand, startVoice, busy, error } = useNexora();
  const [command, setCommand] = useState("");
  const [spoken, setSpoken] = useState(false);
  const [localError, setLocalError] = useState("");
  const phase = !connected ? "OFFLINE" : busy ? "PROCESSING" : voiceState !== "idle"
    ? voiceState.toUpperCase() : brainState?.stage || "STANDBY";
  const metric = (value?: number, suffix = "") => connected && typeof value === "number" ? `${value.toFixed(0)}${suffix}` : "--";
  const links = [["brain", "Cognitive core"], ["voice", "Voice interface"], ["vision", "Visual perception"],
    ["agents", "Agent operations"], ["memory", "Memory archive"], ["workflows", "Workflow studio"]];
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!command.trim() || busy || !connected) return;
    const result = await sendCommand(command, { speak: spoken });
    if (result) setCommand("");
  }
  return <div className="jarvis-console">
    <div className="j-heading"><div><span className="j-eyebrow">PERSONAL INTELLIGENCE / COMMAND DECK</span>
      <h1>At your command.</h1></div><span className={`j-link ${connected ? "" : "j-warning"}`}>
        {connected ? "LIVE TELEMETRY" : "AWAITING CONNECTION"}</span></div>
    <div className="j-workspace">
      <section className="j-panel j-telemetry"><h2>System telemetry <span>01</span></h2>
        {[["PROCESSOR", status?.cpu], ["MEMORY", status?.ram], ["GPU", status?.gpu?.utilization]].map(([label, value]) =>
          <div className="j-meter" key={String(label)}><div><span>{label}</span><strong>{metric(value as number, "%")}</strong></div>
            <progress aria-label={String(label)} max="100" value={connected && typeof value === "number" ? value : 0} /></div>)}
        <dl className="j-facts"><dt>Active agents</dt><dd>{metric(status?.active_agents)}</dd>
          <dt>Running workflows</dt><dd>{metric(status?.active_workflows)}</dd>
          <dt>Stored memories</dt><dd>{metric(status?.memories)}</dd>
          <dt>Events / second</dt><dd>{metric(status?.events_per_sec)}</dd>
          <dt>Event errors</dt><dd>{metric(status?.event_errors)}</dd></dl>
        <div className="j-caption">Values received from your local runtime.</div>
      </section>
      <section className="j-core" aria-label="Jarvis runtime state">
        <span className="j-eyebrow">J.A.R.V.I.S. / INTELLIGENCE INTERFACE</span>
        <div className={`j-reactor ${busy ? "j-active" : ""}`} aria-hidden="true"><div className="j-ring j-ring-one" />
          <div className="j-ring j-ring-two" /><div className="j-ring j-ring-three" /><div className="j-heart">J</div></div>
        <span className="j-phase">{phase.replaceAll("_", " ")}</span>
        <p>{connected ? "One interface. Your tools, context and memory." : "Start the desktop runtime to connect your systems."}</p>
        <div className="j-core-foot"><span>MODEL {connected ? brainState?.active_model || "NOT SELECTED" : "UNAVAILABLE"}</span>
          <span>VOICE {connected ? voiceState.toUpperCase() : "UNAVAILABLE"}</span></div>
      </section>
      <section className="j-panel j-operation"><h2>Current operation <span>02</span></h2>
        <span className="j-eyebrow">OBJECTIVE</span><p className="j-objective">{connected ? brainState?.current_goal || "No task running." : "Runtime unavailable."}</p>
        <dl className="j-facts"><dt>Capability</dt><dd>{connected ? brainState?.selected_capability || "None selected" : "--"}</dd>
          <dt>Verification</dt><dd>{connected ? cognitionState?.last_monitor?.verification_succeeded ? "Verified" : "Not verified" : "--"}</dd></dl>
        <h2 className="j-subheading">Subsystems</h2><div className="j-subsystems">
          {connected ? modules.slice(0, 6).map(module => <div key={module.name}><span>{module.name.replaceAll("_", " ")}</span><small>{module.status}</small></div>) : <p>No live subsystem data.</p>}
        </div>
      </section>
    </div>
    <section className="j-command"><div className="j-response" role="status"><span>JARVIS</span><p>{lastMessage}</p></div>
      {(error || localError) && <p role="alert" className="j-warning">{error || localError}</p>}
      <form onSubmit={submit}><button type="button" aria-label="Listen through microphone" disabled={!connected || busy}
        onClick={async () => { setLocalError(""); try { await startVoice(); } catch (e) { setLocalError(String(e)); } }}><Mic size={18} /></button>
        <input aria-label="Command Jarvis" value={command} onChange={e => setCommand(e.target.value)} placeholder="Ask a question. Give an instruction. Start something." disabled={!connected} />
        <button type="button" aria-label="Speak responses" aria-pressed={spoken} className={spoken ? "j-selected" : ""} onClick={() => setSpoken(!spoken)}><Volume2 size={18} /></button>
        <button type="submit" aria-label="Send command" disabled={!connected || busy || !command.trim()}><Send size={18} /></button></form>
    </section>
    <div className="j-navigation">{links.map(([tab, label]) => <button key={tab} onClick={() => onNavigate?.(tab)}>{label}<ArrowUpRight size={14} /></button>)}</div>
    <section className="j-event-strip"><span className="j-eyebrow">EVENT STREAM</span>
      {connected && events.length ? events.slice(-3).reverse().map(event => <span key={event.sequence}><small>#{event.sequence}</small> {event.topic}</span>) : <span>Waiting for runtime events.</span>}</section>
  </div>;
}
