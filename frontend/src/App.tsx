import { useEffect, useState } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { LogOut, Plus } from "lucide-react";
import { currentUser, getHealth, logout, type User } from "./api/client";
import { clearToken } from "./api/session";
import type { HealthResponse } from "./api/types";
import BackButton from "./components/BackButton";
import HistoryList from "./components/HistoryList";
import LogoMark from "./landing/components/LogoMark";
import { useHistory } from "./hooks/useHistory";
import AnalysisPage from "./pages/AnalysisPage";
import NewAnalysisPage from "./pages/NewAnalysisPage";

type HealthState = { status: "loading" } | { status: "ok"; data: HealthResponse } | { status: "offline" };

// Shows whether the backend is in demo mode, live with a real model, or offline.
function StatusBadge({ health }: { health: HealthState }) {
  if (health.status === "loading") return <span className="badge">Connecting…</span>;
  if (health.status === "offline") return <span className="badge badge-danger">Backend offline</span>;
  if (health.data.mock_mode) return <span className="badge badge-warn">Demo mode</span>;
  return (
    <span className="badge badge-ok" title={`Provider: ${health.data.provider}`}>
      <span className="live-dot" aria-hidden="true" />
      Live · {health.data.model}
    </span>
  );
}

// Lays out the header, history sidebar and the routed main page.
export default function App() {
  const history = useHistory();
  const [health, setHealth] = useState<HealthState>({ status: "loading" });
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    currentUser()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  // Ends the session on the server, forgets the token and returns to the login page.
  const onLogout = async () => {
    await logout().catch(() => undefined);
    clearToken();
    window.location.assign("/login");
  };

  useEffect(() => {
    getHealth()
      .then((data) => setHealth({ status: "ok", data }))
      .catch(() => setHealth({ status: "offline" }));
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" className="brand" aria-label="Sift, new analysis">
          <LogoMark size={26} />
          <span className="brand-word">Sift</span>
        </Link>
        <div className="header-actions">
          <StatusBadge health={health} />
          {user && <span className="header-user">{user.email}</span>}
          <button type="button" className="btn btn-ghost" onClick={onLogout}>
            <LogOut size={15} strokeWidth={1.75} aria-hidden="true" />
            Log out
          </button>
        </div>
      </header>
      <div className="app-body">
        <aside className="sidebar">
          <Link to="/" className="btn btn-primary btn-block">
            <Plus size={16} strokeWidth={1.75} aria-hidden="true" />
            New analysis
          </Link>
          <HistoryList history={history} />
        </aside>
        <main className="main">
          <BackButton />
          <Routes>
            <Route path="/" element={<NewAnalysisPage onCreated={history.addRecord} />} />
            <Route path="/analyses/:id" element={<AnalysisPage onDeleted={history.removeItem} />} />
            <Route
              path="*"
              element={
                <div className="card empty">
                  <h2>Page not found</h2>
                  <Link to="/">Go to a new analysis</Link>
                </div>
              }
            />
          </Routes>
        </main>
      </div>
    </div>
  );
}
