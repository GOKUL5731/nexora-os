import React, { useCallback, useEffect, useState } from "react";
import { BookOpenCheck, GraduationCap, Play, RefreshCw } from "lucide-react";
import { LearningJob, nexoraApi } from "../../../api/client";

export function LearningPage() {
  const [status, setStatus] = useState<Record<string, unknown>>({});
  const [jobs, setJobs] = useState<LearningJob[]>([]);
  const [domain, setDomain] = useState("");
  const [goal, setGoal] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await nexoraApi.learningJobs(30);
      setStatus(data.status ?? {});
      setJobs(data.jobs ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const start = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!domain.trim()) return;
    setLoading(true);
    setError("");
    try {
      await nexoraApi.learningStart(domain, goal);
      setDomain("");
      setGoal("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const counts = (status.jobs ?? {}) as Record<string, number>;

  return (
    <div className="g-page">
      <section className="g-page-hero">
        <div>
          <p className="g-eyebrow">Learning</p>
          <h1>Durable learning jobs with self-test evidence.</h1>
          <p>Learning here means indexing source-attributed knowledge, checking recall, and writing memory evidence. It does not pretend to retrain a model.</p>
        </div>
        <button onClick={refresh} disabled={loading} className="g-secondary-action">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </section>

      {error && <div className="g-empty-inline" role="alert"><GraduationCap className="h-5 w-5" /><p>{error}</p></div>}

      <section className="g-card-grid g-card-grid-three">
        {["PENDING", "RUNNING", "PASSED", "FAILED"].map((key) => (
          <article key={key} className="g-system-card">
            <div className="g-card-topline"><span className="g-card-icon"><BookOpenCheck className="h-4 w-4" /></span></div>
            <h2>{key}</h2>
            <p>{counts[key] ?? 0} jobs</p>
          </article>
        ))}
      </section>

      <section className="g-panel">
        <div className="g-section-heading">
          <span>Create learning job</span>
          <small>real backend execution</small>
        </div>
        <form onSubmit={start} className="grid gap-3 md:grid-cols-[1fr_1.5fr_auto]">
          <input className="g-input" value={domain} onChange={(event) => setDomain(event.target.value)} placeholder="Domain, e.g. FastAPI" aria-label="Learning domain" />
          <input className="g-input" value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="Goal, optional" aria-label="Learning goal" />
          <button disabled={loading || !domain.trim()} className="g-primary-action">
            <Play className="h-4 w-4" />
            Start
          </button>
        </form>
      </section>

      <section className="g-panel">
        <div className="g-section-heading">
          <span>Recent jobs</span>
          <small>{jobs.length} visible</small>
        </div>
        {jobs.length === 0 ? (
          <div className="g-empty-inline">
            <GraduationCap className="h-6 w-6" />
            <p>No learning jobs have been created yet.</p>
          </div>
        ) : (
          <div className="g-event-list">
            {jobs.map((job) => (
              <div key={job.id}>
                <span>{job.status}</span>
                <strong>{job.domain}</strong>
                <small>{job.goal}</small>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
