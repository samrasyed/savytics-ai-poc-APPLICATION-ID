import { NavLink } from "react-router-dom";
import type { HistoryState } from "../hooks/useHistory";
import { formatDateTime } from "../utils/format";
import ErrorBanner from "./ErrorBanner";

// Lists saved analyses, newest first, with paging and error handling.
export default function HistoryList({ history }: { history: HistoryState }) {
  const { items, total, loading, error, hasMore, refresh, loadMore } = history;

  return (
    <section className="history">
      <div className="history-head">
        <h2 className="eyebrow">History</h2>
        <span className="count-pill">{total}</span>
      </div>

      {error ? <ErrorBanner error={error} onRetry={refresh} /> : null}

      {!loading && !error && items.length === 0 ? (
        <p className="muted small">No analyses yet. Your results will appear here.</p>
      ) : null}

      <ul className="history-list">
        {items.map((item) => (
          <li key={item.id}>
            <NavLink
              to={`/analyses/${item.id}`}
              className={({ isActive }) => `history-item${isActive ? " active" : ""}`}
            >
              <span className="history-title">{item.title}</span>
              <span className="muted small">
                {formatDateTime(item.created_at)} · {item.action_item_count} action
                {item.action_item_count === 1 ? "" : "s"}
              </span>
            </NavLink>
          </li>
        ))}
      </ul>

      {loading ? <p className="muted small">Loading…</p> : null}
      {hasMore && !loading ? (
        <button type="button" className="btn btn-block" onClick={loadMore}>
          Load more
        </button>
      ) : null}
    </section>
  );
}
