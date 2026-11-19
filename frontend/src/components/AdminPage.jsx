import { useEffect, useState } from "react";
import { api } from "../api.js";
import { VERDICTS } from "./Results.jsx";

export default function AdminPage() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.adminStats().then(setStats).catch((err) => setError(err.message));
  }, []);

  if (error) return <p className="error" role="alert">{error}</p>;
  if (!stats) return <p className="loading">Loading…</p>;

  return (
    <section className="card">
      <h2>Platform overview</h2>
      <div className="stats">
        <div><span className="number">{stats.users}</span> users</div>
        <div><span className="number">{stats.runs}</span> verification runs</div>
      </div>
      <h3>Runs by verdict</h3>
      <ul>
        {Object.entries(stats.runs_by_verdict).map(([v, n]) => <li key={v}>{VERDICTS[v]?.title || v}: {n}</li>)}
      </ul>
      <h3>Provers</h3>
      <ul>
        {stats.provers.map((p) => (
          <li key={p.name}>{p.label}: {p.available ? `installed (v${p.version || "?"})` : "not installed"}</li>
        ))}
      </ul>
    </section>
  );
}
