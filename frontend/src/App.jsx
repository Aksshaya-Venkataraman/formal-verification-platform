import { useEffect, useState } from "react";
import { api } from "./api.js";
import AdminPage from "./components/AdminPage.jsx";
import AuthForm from "./components/AuthForm.jsx";
import HistoryPage from "./components/HistoryPage.jsx";
import ProblemsPage from "./components/ProblemsPage.jsx";
import VerifyPage from "./components/VerifyPage.jsx";

const TABS = [
  { id: "verify", label: "Verify" },
  { id: "history", label: "History" },
  { id: "problems", label: "My problems" },
];

export default function App() {
  const [user, setUser] = useState(undefined); // undefined = still loading
  const [tab, setTab] = useState("verify");
  const [draft, setDraft] = useState(null); // problem handed to the editor from another tab

  useEffect(() => {
    api.me().then((data) => setUser(data.user)).catch(() => setUser(null));
  }, []);

  function openInEditor(problem) {
    setDraft({ ...problem, key: Date.now() });
    setTab("verify");
  }

  async function logout() {
    await api.logout().catch(() => {});
    setUser(null);
    setTab("verify");
  }

  if (user === undefined) return <p className="loading">Loading…</p>;

  const tabs = user?.is_admin ? [...TABS, { id: "admin", label: "Admin" }] : TABS;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true">⊢</span>
          <div>
            <h1>Formal Verification Platform</h1>
            <p className="tagline">First-order logic checked by SPASS, Vampire and Otter</p>
          </div>
        </div>
        {user && (
          <div className="account">
            <span className="email">{user.email}</span>
            <button type="button" className="link" onClick={logout}>Log out</button>
          </div>
        )}
      </header>

      {!user ? (
        <AuthForm onAuthenticated={setUser} />
      ) : (
        <>
          <nav className="tabs" aria-label="Sections">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                className={tab === t.id ? "tab active" : "tab"}
                aria-current={tab === t.id ? "page" : undefined}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </nav>
          <main>
            {tab === "verify" && <VerifyPage draft={draft} />}
            {tab === "history" && <HistoryPage onOpen={openInEditor} />}
            {tab === "problems" && <ProblemsPage onOpen={openInEditor} />}
            {tab === "admin" && user.is_admin && <AdminPage />}
          </main>
        </>
      )}
      <footer className="footer">
        Problems use the <a href="https://tptp.org/TPTP/SyntaxBNF.html" rel="noreferrer noopener" target="_blank">TPTP</a> FOF/CNF syntax.
      </footer>
    </div>
  );
}
