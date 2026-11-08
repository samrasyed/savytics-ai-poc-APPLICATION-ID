import type { Decision } from "../../api/types";
import { BasisTag, Empty, Evidence, Section, Tag } from "./ui";

const STATUS: Record<Decision["status"], { label: string; tone: "neutral" | "ok" | "warn" | "danger" | "info" }> = {
  confirmed: { label: "Confirmed", tone: "ok" },
  proposed: { label: "Proposed", tone: "neutral" },
  rejected: { label: "Rejected", tone: "danger" },
  pending: { label: "Pending", tone: "warn" },
  changed: { label: "Changed", tone: "info" },
};

const ORDER: Decision["status"][] = ["confirmed", "changed", "pending", "proposed", "rejected"];

// Lists decisions grouped by status, with the decision maker and supporting quote.
export default function DecisionsSection({ decisions }: { decisions: Decision[] }) {
  const sorted = [...decisions].sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status));

  return (
    <Section
      title="Decisions"
      count={decisions.length}
      description="Suggestions and discussions are never shown as confirmed decisions."
    >
      {sorted.length === 0 ? (
        <Empty>No decisions were found.</Empty>
      ) : (
        <ul className="item-list">
          {sorted.map((d) => (
            <li key={d.description} className="item-card">
              <div className="item-head">
                <span className="item-title">{d.description}</span>
                <span className="tag-row">
                  <Tag tone={STATUS[d.status].tone}>{STATUS[d.status].label}</Tag>
                  <BasisTag basis={d.basis} />
                </span>
              </div>
              <p className="small">
                <span className="muted">Decision maker: </span>
                {d.decision_maker ?? <span className="muted">Not identified</span>}
              </p>
              {d.previous_decision ? (
                <p className="small">
                  <span className="muted">Replaces: </span>
                  {d.previous_decision}
                </p>
              ) : null}
              <Evidence text={d.evidence} status={d.evidence_status} />
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
