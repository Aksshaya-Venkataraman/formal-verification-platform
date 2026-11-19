import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { ResultsTable } from "./Results.jsx";

const STARTER = `% Write a problem in TPTP (fof or cnf), or pick an example above.
fof(all_men_mortal, axiom, ![X]: (man(X) => mortal(X))).
fof(socrates_man, axiom, man(socrates)).
fof(socrates_mortal, conjecture, mortal(socrates)).
`;

function describeError(err) {
  if (err.code === "syntax_error") return `Syntax error at line ${err.body.line}, column ${err.body.column}: ${err.message}`;
  const detail = err.body?.details?.[0];
  return detail ? `${detail.field}: ${detail.message}` : err.message;
}

export default function VerifyPage({ draft }) {
  const [provers, setProvers] = useState([]);
  const [maxTime, setMaxTime] = useState(30);
  const [examples, setExamples] = useState([]);
  const [selected, setSelected] = useState([]);
  const [title, setTitle] = useState("Socrates is mortal");
  const [source, setSource] = useState(STARTER);
  const [timeLimit, setTimeLimit] = useState(10);
  const [run, setRun] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.provers().then((data) => {
      setProvers(data.provers);
      setMaxTime(data.max_time_limit);
      setSelected(data.provers.filter((p) => p.available).map((p) => p.name));
    }).catch((err) => setMessage({ tone: "error", text: err.message }));
    api.examples().then((data) => setExamples(data.examples)).catch(() => {});
  }, []);

  useEffect(() => {
    if (draft) {
      setTitle(draft.title);
      setSource(draft.source);
      setRun(null);
      setMessage(null);
    }
  }, [draft]);

  const byDomain = useMemo(() => {
    const groups = {};
    for (const ex of examples) (groups[ex.domain] ||= []).push(ex);
    return groups;
  }, [examples]);

  function loadExample(id) {
    const ex = examples.find((e) => e.id === id);
    if (!ex) return;
    setTitle(ex.title);
    setSource(ex.source);
    setRun(null);
    setMessage({ tone: "info", text: `${ex.description} Expected answer: ${ex.expected}.` });
  }

  function toggle(name) {
    setSelected((cur) => (cur.includes(name) ? cur.filter((n) => n !== name) : [...cur, name]));
  }

  async function guard(action) {
    setBusy(true);
    setMessage(null);
    try {
      await action();
    } catch (err) {
      setMessage({ tone: "error", text: describeError(err) });
    } finally {
      setBusy(false);
    }
  }

  const check = () => guard(async () => {
    const info = await api.validate(source);
    setMessage({
      tone: "ok",
      text: `Syntax OK: ${info.formulas} formula(s), ${info.has_conjecture ? "with" : "without"} a conjecture. ` +
        `Predicates: ${info.predicates.join(", ") || "none"}.`,
    });
  });

  const verify = () => guard(async () => {
    setRun(null);
    setRun(await api.verify({ source, provers: selected, time_limit: Number(timeLimit), title: title || "Untitled problem" }));
  });

  const save = () => guard(async () => {
    await api.saveProblem({ title, domain: "General", description: "", source });
    setMessage({ tone: "ok", text: `Saved "${title}" to your problems.` });
  });

  return (
    <div className="verify">
      <section className="card">
        <div className="row">
          <label className="grow">
            Example problems
            <select defaultValue="" onChange={(e) => loadExample(e.target.value)}>
              <option value="" disabled>Choose an example…</option>
              {Object.entries(byDomain).map(([domain, items]) => (
                <optgroup key={domain} label={domain}>
                  {items.map((ex) => <option key={ex.id} value={ex.id}>{ex.title}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          <label className="grow">
            Title
            <input value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} />
          </label>
        </div>

        <label>
          Problem (TPTP)
          <textarea
            className="editor"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            spellCheck={false}
            rows={14}
            maxLength={65536}
            aria-describedby="tptp-help"
          />
        </label>
        <p id="tptp-help" className="hint">
          <code>!</code> for all, <code>?</code> exists, <code>~</code> not, <code>&amp;</code> and, <code>|</code> or,
          {" "}<code>=&gt;</code> implies, <code>&lt;=&gt;</code> iff. Variables start with an upper-case letter.
        </p>

        <fieldset className="provers">
          <legend>Provers</legend>
          {provers.map((p) => (
            <label key={p.name} className={p.available ? "check" : "check disabled"}>
              <input
                type="checkbox"
                checked={selected.includes(p.name)}
                disabled={!p.available}
                onChange={() => toggle(p.name)}
              />
              {p.label} {p.version ? <small>v{p.version}</small> : <small>(not installed)</small>}
            </label>
          ))}
          <label className="time">
            Time limit (s)
            <input type="number" min={1} max={maxTime} value={timeLimit} onChange={(e) => setTimeLimit(e.target.value)} />
          </label>
        </fieldset>

        <div className="actions">
          <button type="button" onClick={check} disabled={busy}>Check syntax</button>
          <button type="button" onClick={save} disabled={busy || !title}>Save problem</button>
          <button type="button" className="primary" onClick={verify} disabled={busy || selected.length === 0}>
            {busy ? "Running…" : "Run provers"}
          </button>
        </div>
        {message && <p className={`message ${message.tone}`} role={message.tone === "error" ? "alert" : "status"}>{message.text}</p>}
      </section>

      {run && <ResultsTable run={run} />}
    </div>
  );
}
