import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, LockKeyhole, RefreshCw, Shield, ShieldAlert } from "lucide-react";
import { nexoraApi, SecurityAuditItem, SecurityStatus } from "../../../api/client";

export function SecurityPage() {
  const [status, setStatus] = useState<SecurityStatus | null>(null);
  const [audit, setAudit] = useState<SecurityAuditItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [security, audits] = await Promise.all([
        nexoraApi.securityStatus(),
        nexoraApi.securityAudit(40),
      ]);
      setStatus(security);
      setAudit(audits.items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const setEmergency = async (active: boolean) => {
    setError("");
    try {
      if (active) {
        await nexoraApi.securityEmergencyStop("frontend_security_lens");
      } else {
        await nexoraApi.securityEmergencyClear();
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const healthStatus = String(status?.health?.status ?? "unknown");
  const emergencyActive = Boolean(status?.emergency_stop);

  return (
    <div className="g-page">
      <section className="g-page-hero">
        <div>
          <p className="g-eyebrow">Security</p>
          <h1>Permission and audit state from the live runtime.</h1>
          <p>Emergency stop, audit logs, and security health are read from the backend. No permission state is simulated.</p>
        </div>
        <button onClick={refresh} disabled={loading} className="g-secondary-action">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </section>

      {error && (
        <div className="g-empty-inline" role="alert">
          <AlertTriangle className="h-5 w-5" />
          <p>{error}</p>
        </div>
      )}

      <section className="g-card-grid g-card-grid-three">
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><Shield className="h-4 w-4" /></span></div>
          <h2>Security database</h2>
          <p>{healthStatus === "online" ? "Audit database is accessible." : String(status?.health?.error ?? "Status unavailable")}</p>
          <span className={`g-live-pill ${healthStatus === "online" ? "g-status-good" : "g-status-warn"}`}>
            {healthStatus}
          </span>
        </article>
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><LockKeyhole className="h-4 w-4" /></span></div>
          <h2>Emergency stop</h2>
          <p>{emergencyActive ? "Sensitive connector execution is blocked." : "Connector execution is allowed by security policy."}</p>
          <span className={`g-live-pill ${emergencyActive ? "g-status-warn" : "g-status-good"}`}>
            {emergencyActive ? "ACTIVE" : "CLEAR"}
          </span>
        </article>
        <article className="g-system-card">
          <div className="g-card-topline"><span className="g-card-icon"><ShieldAlert className="h-4 w-4" /></span></div>
          <h2>Control</h2>
          <p>Use emergency stop only when G should stop sensitive automation immediately.</p>
          <div className="flex gap-2 mt-3">
            <button onClick={() => setEmergency(true)} disabled={emergencyActive} className="g-secondary-action">
              Stop
            </button>
            <button onClick={() => setEmergency(false)} disabled={!emergencyActive} className="g-primary-action">
              Clear
            </button>
          </div>
        </article>
      </section>

      <section className="g-panel">
        <div className="g-section-heading">
          <span>Recent audit entries</span>
          <small>{audit.length} visible</small>
        </div>
        {audit.length === 0 ? (
          <div className="g-empty-inline">
            <CheckCircle2 className="h-6 w-6" />
            <p>No audit entries returned yet.</p>
          </div>
        ) : (
          <div className="g-event-list">
            {audit.map((item, index) => (
              <div key={`${item.timestamp}-${index}`}>
                <span>{item.method} {item.status}</span>
                <strong>{item.endpoint}</strong>
                <small>{new Date(item.timestamp * 1000).toLocaleString()} · {item.ip}</small>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
