export const VERDICTS = {
  theorem: { tone: "good", title: "Proved", text: "The conjecture follows from the axioms." },
  unsatisfiable: { tone: "good", title: "Unsatisfiable", text: "The formulas contradict each other (refutation found)." },
  counter_satisfiable: { tone: "warn", title: "Not a theorem", text: "A counter-model exists: the conjecture does not follow." },
  satisfiable: { tone: "warn", title: "Satisfiable", text: "The formulas are consistent (a model exists)." },
  unknown: { tone: "muted", title: "Unknown", text: "No prover reached a result within the time limit." },
  conflict: { tone: "bad", title: "Provers disagree", text: "Results contradict each other. Check the problem carefully." },
};

const STATUS_TONE = {
  Theorem: "good",
  Unsatisfiable: "good",
  CounterSatisfiable: "warn",
  Satisfiable: "warn",
  Timeout: "muted",
  GaveUp: "muted",
  Unavailable: "muted",
  Error: "bad",
};

export function StatusBadge({ status }) {
  return <span className={`badge ${STATUS_TONE[status] || "muted"}`}>{status}</span>;
}

export function VerdictBanner({ verdict }) {
  const info = VERDICTS[verdict] || VERDICTS.unknown;
  return (
    <div className={`verdict ${info.tone}`} role="status">
      <strong>{info.title}</strong>
      <span>{info.text}</span>
    </div>
  );
}

const LABELS = { spass: "SPASS", vampire: "Vampire", otter: "Otter" };

export function ResultsTable({ run }) {
  return (
    <section className="results">
      <VerdictBanner verdict={run.verdict} />
      <table>
        <thead>
          <tr>
            <th scope="col">Prover</th>
            <th scope="col">Result</th>
            <th scope="col">Time</th>
          </tr>
        </thead>
        <tbody>
          {run.results.map((r) => (
            <tr key={r.prover}>
              <td>{LABELS[r.prover] || r.prover}</td>
              <td><StatusBadge status={r.status} /></td>
              <td>{r.seconds.toFixed(2)} s</td>
            </tr>
          ))}
        </tbody>
      </table>
      {run.results.map((r) => (
        <details key={r.prover} className="output">
          <summary>{LABELS[r.prover] || r.prover} output</summary>
          {/* Rendered as text by React, so prover output can never inject HTML. */}
          <pre>{r.output || "(no output)"}</pre>
        </details>
      ))}
    </section>
  );
}
