import { Link } from "react-router-dom";
import type { ConflictValue, Contradiction, ModuleState } from "../../api/types";
import { Empty, Evidence, Section, Tag, humanize } from "./ui";
import ModuleNotice from "./ModuleNotice";

// Shows which document a value came from, linking to earlier analyses.
function SourceLink({ value }: { value: ConflictValue }) {
  if (value.is_current) return <span>This document</span>;
  if (!value.document_id) return <span className="muted">Earlier document</span>;
  return <Link to={`/analyses/${value.document_id}`}>{value.document_title ?? "Earlier document"}</Link>;
}

// Renders one contradiction with each conflicting value, its source and supporting sentence.
function ContradictionCard({ conflict }: { conflict: Contradiction }) {
  return (
    <li className="item-card">
      <div className="item-head">
        <span className="item-title">{conflict.description}</span>
        <span className="tag-row">
          <Tag>{humanize(conflict.conflict_type)}</Tag>
          <Tag tone="info">{conflict.scope === "cross_document" ? "Across documents" : "Within document"}</Tag>
          <Tag tone={conflict.resolution_status === "resolved" ? "ok" : "warn"}>
            {humanize(conflict.resolution_status)}
          </Tag>
        </span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Conflicting value</th>
              <th>Source document</th>
              <th>Supporting sentence</th>
            </tr>
          </thead>
          <tbody>
            {conflict.values.map((v) => (
              <tr key={`${v.value}-${v.document_id}`}>
                <td className="strong">{v.value}</td>
                <td>
                  <SourceLink value={v} />
                </td>
                <td>
                  <Evidence text={v.evidence} status={v.evidence_status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {conflict.suggested_action ? (
        <p className="small">
          <span className="muted">Suggested action: </span>
          {conflict.suggested_action}
        </p>
      ) : null}
    </li>
  );
}

// Lists conflicting statements found within this document or against earlier documents.
export default function ContradictionsSection({
  contradictions,
  state,
  compared,
}: {
  contradictions: Contradiction[];
  state: ModuleState | undefined;
  compared: number;
}) {
  return (
    <Section
      title="Contradictions"
      count={contradictions.length}
      description={`Checked within this document and against ${compared} earlier ${compared === 1 ? "document" : "documents"}. No value is chosen as correct.`}
    >
      <ModuleNotice state={state} />
      {state === "ok" && contradictions.length === 0 ? <Empty>No contradictions were found.</Empty> : null}
      {contradictions.length > 0 ? (
        <ul className="item-list">
          {contradictions.map((c) => (
            <ContradictionCard key={c.description} conflict={c} />
          ))}
        </ul>
      ) : null}
    </Section>
  );
}
