import { useState } from "react";
import { api } from "../api.js";

export default function AuthForm({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = mode === "login" ? await api.login(email, password) : await api.register(email, password);
      onAuthenticated(data.user);
    } catch (err) {
      const detail = err.body?.details?.[0];
      setError(detail ? `${detail.field}: ${detail.message}` : err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card auth">
      <h2>{mode === "login" ? "Log in" : "Create an account"}</h2>
      <form onSubmit={submit}>
        <label>
          Email
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            minLength={mode === "register" ? 12 : 1}
            maxLength={128}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {mode === "register" && <p className="hint">At least 12 characters. A passphrase works well.</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
        </button>
      </form>
      <button type="button" className="link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
        {mode === "login" ? "New here? Create an account" : "Already have an account? Log in"}
      </button>
    </section>
  );
}
