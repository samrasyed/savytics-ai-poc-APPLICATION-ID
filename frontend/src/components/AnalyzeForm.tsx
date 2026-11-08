import { useEffect, useState, type FormEvent } from "react";
import { analyze } from "../api/client";
import { MAX_TEXT_CHARS, MAX_TITLE_CHARS, type AnalysisRecord } from "../api/types";
import ErrorBanner from "./ErrorBanner";

const SAMPLE_TITLE = "Weekly product sync";
const SAMPLE_TEXT = `Weekly sync transcript. Attendees: Priya, Marco, Lena.
Priya: The billing page redesign is our top priority; I'll draft the pricing copy by Friday.
Marco: The CSV export still times out for big accounts. It's a blocker, I'll take it.
Lena: We haven't decided whether to delay push notifications. Budget for QA is unconfirmed.
Someone needs to book the design review next week.`;

interface Props {
  onCreated: (record: AnalysisRecord) => void;
}

// Counts seconds while a request is running so the user sees progress.
function useElapsedSeconds(running: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!running) return;
    setSeconds(0);
    const timer = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  return seconds;
}

// Collects a title and document text, validates them and sends them for analysis.
export default function AnalyzeForm({ onCreated }: Props) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const elapsed = useElapsedSeconds(submitting);

  const titleTooLong = title.trim().length > MAX_TITLE_CHARS;
  const textTooLong = text.trim().length > MAX_TEXT_CHARS;
  const isEmpty = !title.trim() || !text.trim();
  const canSubmit = !submitting && !isEmpty && !titleTooLong && !textTooLong;

  // Sends the document to the backend and reports the saved result.
  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      onCreated(await analyze(title.trim(), text));
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  // Handles the form submit event.
  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (canSubmit) void submit();
  }

  // Fills the form with an example meeting transcript.
  function loadSample() {
    setTitle(SAMPLE_TITLE);
    setText(SAMPLE_TEXT);
    setError(null);
  }

  return (
    <form className="card form" onSubmit={handleSubmit}>
      <div className="form-head poster">
        <div>
          <p className="eyebrow">
            <span className="live-dot" aria-hidden="true" />
            Text in. Clarity out.
          </p>
          <h1>Analyze a document</h1>
          <p className="meta">
            Paste meeting notes, a project brief or a report. You get a summary and key points up
            top, plus entities, action items, decisions, contradictions, risks, dependencies and
            open questions.
          </p>
        </div>
        <button type="button" className="btn" onClick={loadSample} disabled={submitting}>
          Use sample
        </button>
      </div>

      <label className="field">
        <span className="field-label">
          Title
          <span className={`counter${titleTooLong ? " over" : ""}`}>
            {title.trim().length}/{MAX_TITLE_CHARS}
          </span>
        </span>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Sprint planning, 12 March"
          disabled={submitting}
        />
      </label>

      <label className="field">
        <span className="field-label">
          Document text
          <span className={`counter${textTooLong ? " over" : ""}`}>
            {text.trim().length.toLocaleString()}/{MAX_TEXT_CHARS.toLocaleString()}
          </span>
        </span>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste your text here…"
          rows={14}
          disabled={submitting}
        />
      </label>

      {titleTooLong || textTooLong ? (
        <p className="warn small">Please shorten the {titleTooLong ? "title" : "text"} to fit the limit.</p>
      ) : null}

      {error ? <ErrorBanner error={error} onRetry={() => void submit()} /> : null}

      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={!canSubmit}>
          {submitting ? `Analyzing… ${elapsed}s` : "Analyze"}
        </button>
        {submitting ? <span className="muted small">Extraction and checks usually take 10–40 seconds.</span> : null}
      </div>
    </form>
  );
}
