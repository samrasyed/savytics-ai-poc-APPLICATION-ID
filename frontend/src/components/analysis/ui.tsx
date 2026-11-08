import type { ReactNode } from "react";
import type { Basis, EvidenceStatus } from "../../api/types";

type Tone = "neutral" | "ok" | "warn" | "danger" | "info";

// Renders a small coloured label.
export function Tag({ tone = "neutral", children, title }: { tone?: Tone; children: ReactNode; title?: string }) {
  return (
    <span className={`tag tag-${tone}`} title={title}>
      {children}
    </span>
  );
}

// Renders a titled card section with an optional count and actions.
export function Section({
  title,
  count,
  description,
  actions,
  children,
}: {
  title: string;
  count?: number;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="card section">
      <div className="section-head">
        <div>
          <h2>
            {title}
            {count !== undefined ? <span className="muted small"> ({count})</span> : null}
          </h2>
          {description ? <p className="muted small section-desc">{description}</p> : null}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

// Shows a muted message for an empty section.
export function Empty({ children }: { children: ReactNode }) {
  return <p className="muted empty-note">{children}</p>;
}

const EVIDENCE_LABELS: Record<EvidenceStatus, { label: string; tone: Tone; title: string } | null> = {
  verified: { label: "Quote verified", tone: "ok", title: "This quote was found word for word in the source." },
  partial: { label: "Quote partly matched", tone: "info", title: "Most of this quote was found in the source." },
  not_found: { label: "Quote not found", tone: "warn", title: "This quote could not be found in the source." },
  missing: null,
};

// Shows a supporting quote with a tag saying whether it was found in the source.
export function Evidence({ text, status }: { text: string | null; status: EvidenceStatus }) {
  if (!text) return <p className="muted small">No supporting quote.</p>;
  const label = EVIDENCE_LABELS[status];
  return (
    <figure className="evidence">
      <blockquote>“{text}”</blockquote>
      {label ? (
        <figcaption>
          <Tag tone={label.tone} title={label.title}>
            {label.label}
          </Tag>
        </figcaption>
      ) : null}
    </figure>
  );
}

const BASIS_LABELS: Record<Basis, { label: string; tone: Tone; title: string }> = {
  fact: { label: "Fact", tone: "ok", title: "Stated directly and backed by a verified quote." },
  inference: { label: "Inference", tone: "info", title: "Deduced from text that was found in the source." },
  assumption: { label: "Assumption", tone: "warn", title: "Not backed by a quote found in the source." },
};

// Shows whether an item is a fact, an inference or an assumption.
export function BasisTag({ basis }: { basis: Basis | null }) {
  if (!basis) return null;
  const { label, tone, title } = BASIS_LABELS[basis];
  return (
    <Tag tone={tone} title={title}>
      {label}
    </Tag>
  );
}

// Turns a snake_case value into readable text.
export function humanize(value: string): string {
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Renders a label and value pair inside a details grid.
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="field-pair">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
