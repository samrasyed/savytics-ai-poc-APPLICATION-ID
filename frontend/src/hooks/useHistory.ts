import { useCallback, useEffect, useState } from "react";
import { ApiError, listAnalyses } from "../api/client";
import type { AnalysisListItem, AnalysisRecord } from "../api/types";

const PAGE_SIZE = 20;

export interface HistoryState {
  items: AnalysisListItem[];
  total: number;
  loading: boolean;
  error: ApiError | null;
  hasMore: boolean;
  refresh: () => void;
  loadMore: () => void;
  addRecord: (record: AnalysisRecord) => void;
  removeItem: (id: string) => void;
}

// Turns a full analysis record into the short form shown in the history list.
function toListItem(record: AnalysisRecord): AnalysisListItem {
  return {
    id: record.id,
    title: record.title,
    created_at: record.created_at,
    summary_preview: record.result.summary.slice(0, 160),
    action_item_count: record.result.action_items.length,
  };
}

// Loads saved analyses page by page and keeps the list in sync with local changes.
export function useHistory(): HistoryState {
  const [items, setItems] = useState<AnalysisListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  // Fetches one page and either replaces or extends the current list.
  const fetchPage = useCallback(async (offset: number, replace: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const page = await listAnalyses(PAGE_SIZE, offset);
      setItems((prev) => (replace ? page.items : [...prev, ...page.items]));
      setTotal(page.total);
    } catch (err) {
      setError(err instanceof ApiError ? err : null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchPage(0, true);
  }, [fetchPage]);

  // Reloads the first page from the server.
  const refresh = useCallback(() => void fetchPage(0, true), [fetchPage]);

  // Loads the next page after the items already shown.
  const loadMore = useCallback(() => void fetchPage(items.length, false), [fetchPage, items.length]);

  // Puts a newly created analysis at the top of the list.
  const addRecord = useCallback((record: AnalysisRecord) => {
    setItems((prev) => [toListItem(record), ...prev.filter((i) => i.id !== record.id)]);
    setTotal((t) => t + 1);
  }, []);

  // Removes a deleted analysis from the list.
  const removeItem = useCallback((id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
    setTotal((t) => Math.max(0, t - 1));
  }, []);

  return {
    items,
    total,
    loading,
    error,
    hasMore: items.length < total,
    refresh,
    loadMore,
    addRecord,
    removeItem,
  };
}
