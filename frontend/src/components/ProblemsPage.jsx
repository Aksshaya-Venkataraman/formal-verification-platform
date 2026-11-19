import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function ProblemsPage({ onOpen }) {
  const [problems, setProblems] = useState([]);
  const [error, setError] = useState("");

  const load = () => api.problems().then((d) => setProblems(d.problems)).catch((err) => setError(err.message));
  useEffect(() => { load(); }, []);

  async function remove(id) {
    await api.deleteProblem(id).catch((err) => setError(err.message));
    load();
  }

  return (
    <section className="card">
      <h2>My problems</h2>
      {error && <p className="error" role="alert">{error}</p>}
      {problems.length === 0 ? (
        <p className="hint">Saved problems appear here. Use “Save problem” on the Verify tab.</p>
      ) : (
        <ul className="problems">
          {problems.map((p) => (
            <li key={p.id}>
              <div>
                <strong>{p.title}</strong>
                <span className="hint"> · {p.domain} · updated {new Date(p.updated_at).toLocaleDateString()}</span>
                {p.description && <p>{p.description}</p>}
              </div>
              <div className="buttons">
                <button type="button" onClick={() => onOpen({ title: p.title, source: p.source })}>Open in editor</button>
                <button type="button" className="danger" onClick={() => remove(p.id)}>Delete</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
