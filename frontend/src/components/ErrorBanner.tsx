import { ApiError } from "../api/client";

interface Props {
  error: unknown;
  onRetry?: () => void;
}

// Shows a friendly error message, a retry button when it can help, and the request ID.
export default function ErrorBanner({ error, onRetry }: Props) {
  const apiError = error instanceof ApiError ? error : null;
  const message = apiError?.message ?? "Something went wrong. Please try again.";
  const canRetry = Boolean(onRetry) && (apiError?.retryable ?? true);

  return (
    <div className="error-banner" role="alert">
      <div>
        <strong>{message}</strong>
        {apiError?.retryAfterSeconds ? (
          <div className="muted">You can try again in about {apiError.retryAfterSeconds} s.</div>
        ) : null}
        {apiError?.requestId ? (
          <div className="muted small">
            {apiError.code} · request {apiError.requestId}
          </div>
        ) : null}
      </div>
      {canRetry ? (
        <button type="button" className="btn" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}
