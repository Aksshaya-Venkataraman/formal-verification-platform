import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { ResultsTable, StatusBadge, VERDICTS } from "./Results.jsx";

const PAGE = 20;

export default function HistoryPage({ onOpen }) {
  const [page, setPage] = useState({ runs: [], total: 0, offset: 0 });
  const [open, setOpen] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback((offset) => {
    api.runs(offset, PAGE).then(setPage).catch((err) => setError(err.message));
  }, []);

  useEffect(() => load(0), [load]);

  async function show(id) {
    try {
      setOpen(await api.run(id));
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(id) {
    await api.deleteRun(id).catch((err) => setError(err.message));
    if (open?.id === id) setOpen(null);
    load(page.offset);
  }

  return (
    <section className="card">
      <h2>Verification history</h2>
      {error && <p className="error" role="alert">{error}</p>}
      {page.runs.length === 0 ? (
        <p className="hint">No runs yet. Verify a problem and it will appear here.</p>
      ) : (
        <table className="list">
          <thead>
            <tr><th scope="col">When</th><th scope="col">Problem</th><th scope="col">Verdict</th><th scope="col">Provers</th><th scope="col"><span className="sr-only">Actions</span></th></tr>
          </thead>
          <tbody>
            {page.runs.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.created_at).toLocaleString()}</td>
                <td>{r.title}</td>
                <td>{VERDICTS[r.verdict]?.title || r.verdict}</td>
                <td className="badges">{Object.entries(r.statuses).map(([p, s]) => <span key={p} title={p}><StatusBadge status={s} /></span>)}</td>
                <td className="buttons">
                  <button type="button" onClick={() => show(r.id)}>Details</button>
                  <button type="button" onClick={() => api.run(r.id).then((full) => onOpen({ title: full.title, source: full.source }))}>Edit</button>
                  <button type="button" className="danger" onClick={() => remove(r.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="pager">
        <button type="button" disabled={page.offset === 0} onClick={() => load(Math.max(0, page.offset - PAGE))}>Newer</button>
        <span>{page.total ? `${page.offset + 1}–${Math.min(page.offset + PAGE, page.total)} of ${page.total}` : ""}</span>
        <button type="button" disabled={page.offset + PAGE >= page.total} onClick={() => load(page.offset + PAGE)}>Older</button>
      </div>
      {open && (
        <div className="detail">
          <h3>{open.title}</h3>
          <pre className="source">{open.source}</pre>
          <ResultsTable run={open} />
        </div>
      )}
    </section>
  );
}
