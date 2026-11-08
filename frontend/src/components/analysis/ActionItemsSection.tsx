import type { ActionItem } from "../../api/types";
import { BasisTag, Empty, Evidence, Field, Section, Tag } from "./ui";

const STATUS: Record<ActionItem["status"], { label: string; tone: "neutral" | "ok" | "warn" | "danger" | "info" }> = {
  open: { label: "Open", tone: "neutral" },
  in_progress: { label: "In progress", tone: "info" },
  done: { label: "Done", tone: "ok" },
  blocked: { label: "Blocked", tone: "danger" },
  unknown: { label: "Status unclear", tone: "warn" },
};

const PRIORITY_TONE = { high: "danger", medium: "warn", low: "ok" } as const;

// Shows the owners, or "Unassigned" when nobody is named.
function Owners({ item }: { item: ActionItem }) {
  if (item.owners.length === 0) return <span className="muted">Unassigned</span>;
  return (
    <>
      {item.owners.join(", ")}
      {item.owners.length > 1 ? <span className="muted small"> (shared)</span> : null}
    </>
  );
}

// Shows the deadline with its confirmed or tentative label, or "Not specified".
function Deadline({ item }: { item: ActionItem }) {
  if (!item.due_date) return <span className="muted">Not specified</span>;
  return (
    <>
      {item.due_date}{" "}
      {item.deadline_type ? (
        <Tag tone={item.deadline_type === "confirmed" ? "ok" : "warn"}>
          {item.deadline_type === "confirmed" ? "Confirmed" : "Tentative"}
        </Tag>
      ) : null}
    </>
  );
}

// Shows the priority and whether it was stated in the text or inferred.
function PriorityValue({ item }: { item: ActionItem }) {
  if (!item.priority) return <span className="muted">Not stated</span>;
  return (
    <>
      <Tag tone={PRIORITY_TONE[item.priority]}>{item.priority}</Tag>{" "}
      <span className="muted small">{item.priority_source === "explicit" ? "stated in text" : "AI-inferred"}</span>
    </>
  );
}

// Renders one task card with all of its details and supporting quote.
function ActionCard({ item }: { item: ActionItem }) {
  const status = STATUS[item.status];
  return (
    <li className="item-card">
      <div className="item-head">
        <span className="item-title">{item.task}</span>
        <span className="tag-row">
          <Tag tone={status.tone}>{status.label}</Tag>
          <BasisTag basis={item.basis} />
        </span>
      </div>
      <dl className="field-grid">
        <Field label="Owner">
          <Owners item={item} />
        </Field>
        <Field label="Deadline">
          <Deadline item={item} />
        </Field>
        <Field label="Priority">
          <PriorityValue item={item} />
        </Field>
        <Field label="Certainty">{item.certainty.charAt(0).toUpperCase() + item.certainty.slice(1)}</Field>
      </dl>
      <Evidence text={item.evidence} status={item.evidence_status} />
    </li>
  );
}

// Lists every task with owner, deadline, status, priority, certainty and evidence.
export default function ActionItemsSection({ items }: { items: ActionItem[] }) {
  return (
    <Section title="Action items" count={items.length}>
      {items.length === 0 ? (
        <Empty>No action items were found in this document.</Empty>
      ) : (
        <ul className="item-list">
          {items.map((item) => (
            <ActionCard key={item.task} item={item} />
          ))}
        </ul>
      )}
    </Section>
  );
}
