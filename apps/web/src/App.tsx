import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, BarChart3, BookOpen, ChevronDown, CircleCheck, Database, FlaskConical, GitCompareArrows, Play, RefreshCw, Settings, ShieldCheck, Target, TriangleAlert } from "lucide-react";
import { createDemo, getProjects, getRuns, startRun, type Metrics, type Project, type Run } from "./api";

const pct = (value: number | null | undefined) => value == null ? "—" : `${(value * 100).toFixed(1)}%`;

function MetricCard({ label, value, tone = "mint", note }: { label: string; value: string; tone?: "mint" | "amber" | "blue" | "rose"; note: string }) {
  return <article className={`metric-card ${tone}`}>
    <div className="metric-label">{label}</div>
    <div className="metric-value">{value}</div>
    <div className="metric-note">{note}</div>
  </article>;
}

function Matrix({ metrics }: { metrics: Metrics }) {
  const labels = ["allow", "block", "escalate"];
  const max = Math.max(1, ...labels.flatMap(e => labels.map(a => metrics.confusion_matrix[e]?.[a] || 0)));
  return <div className="matrix" role="table" aria-label="Confusion matrix">
    <div /><div className="axis">Allow</div><div className="axis">Block</div><div className="axis">Escalate</div>
    {labels.map(expected => <div className="matrix-row" key={expected}>
      <div className="axis row-axis">{expected}</div>
      {labels.map(actual => {
        const count = metrics.confusion_matrix[expected]?.[actual] || 0;
        return <div className={`matrix-cell ${expected === actual ? "correct" : "wrong"}`} style={{ "--strength": Math.max(.08, count / max) } as React.CSSProperties} key={actual}>
          <strong>{count}</strong><span>{expected === actual ? "correct" : "mismatch"}</span>
        </div>;
      })}
    </div>)}
  </div>;
}

export function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const loadProjects = useCallback(async () => {
    try {
      const data = await getProjects();
      setProjects(data);
      setSelected(current => current || data[0]?.id || "");
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load projects"); }
    finally { setLoading(false); }
  }, []);

  const loadRuns = useCallback(async () => {
    if (!selected) { setRuns([]); return; }
    try { setRuns(await getRuns(selected)); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load runs"); }
  }, [selected]);

  useEffect(() => { void loadProjects(); }, [loadProjects]);
  useEffect(() => { void loadRuns(); const timer = window.setInterval(() => void loadRuns(), 3000); return () => clearInterval(timer); }, [loadRuns]);

  const latest = useMemo(() => runs.find(run => run.metrics) || null, [runs]);
  const metrics = latest?.metrics;
  const activeProject = projects.find(project => project.id === selected);

  const bootstrap = async () => {
    setCreating(true);
    try { const project = await createDemo(); await loadProjects(); setSelected(project.id); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Demo creation failed"); }
    finally { setCreating(false); }
  };

  const launchRun = async () => {
    if (!selected) return;
    setCreating(true);
    try {
      await startRun(selected);
      await loadRuns();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Evaluation failed to start");
    } finally {
      setCreating(false);
    }
  };

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><ShieldCheck size={20}/></div><div><strong>GuardBench</strong><span>Decision reliability</span></div></div>
      <nav>
        <a className="active"><BarChart3 size={17}/>Overview</a>
        <a><BookOpen size={17}/>Datasets</a>
        <a><Target size={17}/>Targets</a>
        <a><Activity size={17}/>Evaluation runs</a>
        <a><GitCompareArrows size={17}/>Comparisons</a>
      </nav>
      <div className="side-footer"><a><Settings size={17}/>Settings</a><div className="status"><span/>Local-first · v0.1 alpha</div></div>
    </aside>
    <main>
      <header>
        <div><div className="eyebrow">Workspace overview</div><h1>{activeProject?.name || "Guardrail evaluation"}</h1></div>
        <div className="header-actions">
          {projects.length > 0 && <label className="project-select"><Database size={16}/><select value={selected} onChange={event => setSelected(event.target.value)}>{projects.map(project => <option value={project.id} key={project.id}>{project.name}</option>)}</select><ChevronDown size={14}/></label>}
          <button className="icon-button" onClick={() => void loadRuns()} aria-label="Refresh"><RefreshCw size={17}/></button>
          <button className="primary" onClick={projects.length ? launchRun : bootstrap} disabled={creating}><Play size={16}/>{creating ? "Preparing…" : projects.length ? "New evaluation" : "Run sample benchmark"}</button>
        </div>
      </header>

      {error && <div className="alert"><TriangleAlert size={17}/><span>{error}</span><small>Check that the API is running on port 8000.</small></div>}
      {loading ? <div className="empty">Loading workspace…</div> : !projects.length ? <section className="hero-empty">
        <div className="hero-icon"><FlaskConical size={28}/></div><div className="eyebrow">Ready when you are</div><h2>Measure guardrails, not hunches.</h2><p>Run a credential-free sample benchmark and inspect allow, block, and escalate decisions in under a minute.</p><button className="primary large" onClick={bootstrap} disabled={creating}><Play size={17}/>{creating ? "Creating sample…" : "Create sample workspace"}</button>
      </section> : <>
        <section className="summary-line"><div><span className={`run-dot ${latest?.status || "idle"}`}/><strong>{latest ? `Latest run ${latest.id.slice(0, 8)}` : "No completed run yet"}</strong><span>{latest?.completed_at ? new Date(latest.completed_at).toLocaleString() : "Evaluation is being prepared"}</span></div><div>{metrics && <><CircleCheck size={16}/>{metrics.scored} of {metrics.attempted} cases scored</>}</div></section>
        <section className="metrics-grid">
          <MetricCard label="Decision accuracy" value={pct(metrics?.accuracy)} note="Across normalized decisions" />
          <MetricCard label="Macro F1" value={pct(metrics?.macro_f1)} tone="blue" note="Equal weight across classes" />
          <MetricCard label="False block rate" value={pct(metrics?.false_block_rate)} tone="amber" note="Safe requests blocked" />
          <MetricCard label="Missed block rate" value={pct(metrics?.missed_block_rate)} tone="rose" note="Restricted requests allowed" />
        </section>
        <section className="content-grid">
          <article className="panel matrix-panel"><div className="panel-heading"><div><span>Decision quality</span><h3>Confusion matrix</h3></div><div className="legend"><span className="good"/>Correct<span className="bad"/>Mismatch</div></div>{metrics ? <Matrix metrics={metrics}/> : <div className="panel-empty">Waiting for a completed evaluation…</div>}<div className="matrix-caption"><span>Expected decision ↓</span><span>Actual decision →</span></div></article>
          <article className="panel"><div className="panel-heading"><div><span>Execution health</span><h3>Recent runs</h3></div><Activity size={20}/></div><div className="run-list">{runs.length ? runs.slice(0, 6).map(run => <div className="run-item" key={run.id}><div className={`run-icon ${run.status}`}>{run.status === "completed" ? <CircleCheck size={16}/> : run.status === "failed" ? <TriangleAlert size={16}/> : <RefreshCw size={16}/>}</div><div><strong>{run.id.slice(0, 8)}</strong><span>{new Date(run.created_at).toLocaleString()}</span></div><div className="run-score">{run.metrics ? pct(run.metrics.accuracy) : run.status}</div></div>) : <div className="panel-empty">The first run will appear here.</div>}</div></article>
        </section>
      </>}
    </main>
  </div>;
}

