import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ApiError, deleteAnalysis, getAnalysis, rerunIntelligence } from "../api/client";
import type { AnalysisRecord } from "../api/types";
import AnalysisView from "../components/AnalysisView";
import ErrorBanner from "../components/ErrorBanner";

// Loads one analysis by ID from the URL and lets the user re-run its checks or delete it.
export default function AnalysisPage({ onDeleted }: { onDeleted: (id: string) => void }) {
  const { id = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const passed = (location.state as { record?: AnalysisRecord } | null)?.record;

  const [record, setRecord] = useState<AnalysisRecord | null>(passed?.id === id ? passed : null);
  const [error, setError] = useState<unknown>(null);
  const [deleting, setDeleting] = useState(false);
  const [rerunning, setRerunning] = useState(false);

  // Fetches the analysis from the backend.
  const load = useCallback(async () => {
    setError(null);
    setRecord(null);
    try {
      setRecord(await getAnalysis(id));
    } catch (err) {
      setError(err);
    }
  }, [id]);

  useEffect(() => {
    if (passed?.id === id) {
      setRecord(passed);
      setError(null);
    } else {
      void load();
    }
  }, [id, passed, load]);

  // Asks for confirmation, deletes the analysis and returns to the new-analysis page.
  async function handleDelete() {
    if (!record || !window.confirm(`Delete "${record.title}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await deleteAnalysis(record.id);
      onDeleted(record.id);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err);
      setDeleting(false);
    }
  }

  // Re-runs the intelligence checks and shows the updated analysis.
  async function handleRerun() {
    if (!record) return;
    setRerunning(true);
    setError(null);
    try {
      const updated = await rerunIntelligence(record.id);
      setRecord(updated);
      navigate(location.pathname, { replace: true, state: { record: updated } });
    } catch (err) {
      setError(err);
    } finally {
      setRerunning(false);
    }
  }

  if (error instanceof ApiError && error.code === "NOT_FOUND") {
    return (
      <div className="card empty">
        <h2>Analysis not found</h2>
        <p className="muted">It may have been deleted.</p>
        <Link to="/">Start a new analysis</Link>
      </div>
    );
  }

  return (
    <>
      {error ? (
        <ErrorBanner error={error} onRetry={record ? () => void handleRerun() : () => void load()} />
      ) : null}
      {record ? (
        <AnalysisView
          record={record}
          deleting={deleting}
          rerunning={rerunning}
          onDelete={() => void handleDelete()}
          onRerun={() => void handleRerun()}
        />
      ) : !error ? (
        <p className="muted">Loading…</p>
      ) : null}
    </>
  );
}
