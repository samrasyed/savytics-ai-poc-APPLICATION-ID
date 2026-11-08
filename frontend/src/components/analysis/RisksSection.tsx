import { Link } from "react-router-dom";
import type { ModuleState, Risk } from "../../api/types";
import { BasisTag, Empty, Evidence, Field, Section, Tag, humanize } from "./ui";
import ModuleNotice from "./ModuleNotice";

const SEVERITY_TONE = { high: "danger", medium: "warn", low: "ok" } as const;
const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 } as const;

// Renders one risk with its severity, origin, reason, evidence, source and mitigation.
function RiskCard({ risk }: { risk: Risk }) {
  const severityNote = risk.severity_source === "explicit" ? "stated in text" : "AI-assessed";
  return (
    <li className="item-card">
      <div className="item-head">
        <span className="item-title">{risk.description}</span>
        <span className="tag-row">
          <Tag tone={SEVERITY_TONE[risk.severity]} title={`Severity is ${severityNote}`}>
            {humanize(risk.severity)} severity
          </Tag>
          <Tag tone={risk.origin === "explicit" ? "neutral" : "info"}>
            {risk.origin === "explicit" ? "Stated risk" : "AI-inferred risk"}
          </Tag>
          <BasisTag basis={risk.basis} />
        </span>
      </div>
      <dl className="field-grid">
        <Field label="Category">{humanize(risk.category)}</Field>
        <Field label="Severity basis">{severityNote}</Field>
        <Field label="Status">{humanize(risk.resolution_status)}</Field>
        <Field label="Source">
          {risk.is_current || !risk.document_id ? (
            "This document"
          ) : (
            <Link to={`/analyses/${risk.document_id}`}>{risk.document_title ?? "Earlier document"}</Link>
          )}
        </Field>
      </dl>
      {risk.reason ? (
        <p className="small">
          <span className="muted">Reason: </span>
          {risk.reason}
        </p>
      ) : null}
      <Evidence text={risk.evidence} status={risk.evidence_status} />
      {risk.mitigation ? (
        <p className="small">
          <span className="muted">Suggested mitigation: </span>
          {risk.mitigation}
        </p>
      ) : null}
    </li>
  );
}

// Lists stated and AI-inferred risks, most severe first.
export default function RisksSection({ risks, state }: { risks: Risk[]; state: ModuleState | undefined }) {
  const sorted = [...risks].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);
  return (
    <Section
      title="Risks"
      count={risks.length}
      description="Severity is the AI's assessment unless the document states it. It is not an assigned priority."
    >
      <ModuleNotice state={state} />
      {state === "ok" && risks.length === 0 ? <Empty>No risks were found.</Empty> : null}
      {sorted.length > 0 ? (
        <ul className="item-list">
          {sorted.map((r) => (
            <RiskCard key={r.description} risk={r} />
          ))}
        </ul>
      ) : null}
    </Section>
  );
}
