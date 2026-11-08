import type { ValidationReport } from "../../api/types";

// Builds short summary lines from the validation counters.
function summaryLines(checks: Record<string, number>): string[] {
  const lines: string[] = [];
  const checked = checks.evidence_checked ?? 0;
  if (checked) {
    const supported = (checks.evidence_verified ?? 0) + (checks.evidence_partial ?? 0);
    lines.push(`${supported} of ${checked} supporting quotes found in the source`);
  }
  const labels: [string, string][] = [
    ["owners_removed", "unverified owners removed"],
    ["deadlines_removed", "deadlines not found in the text removed"],
    ["invalid_dates", "date problems found"],
    ["duplicates_merged", "duplicates merged"],
    ["entities_removed", "entities not found in the text removed"],
    ["items_dropped", "unsupported items dropped"],
    ["questions_added", "gaps added to open questions"],
  ];
  for (const [key, label] of labels) {
    if (checks[key]) lines.push(`${checks[key]} ${label}`);
  }
  return lines;
}

// Shows what the automatic validation checked, changed and flagged.
export default function ValidationNotes({ report }: { report: ValidationReport }) {
  const lines = summaryLines(report.checks);
  const warnings = report.issues.filter((i) => i.level === "warning").length;

  return (
    <details className="card source">
      <summary>
        Validation checks{" "}
        <span className="muted small">
          {warnings ? `· ${warnings} warning${warnings === 1 ? "" : "s"}` : "· no warnings"}
        </span>
      </summary>
      <div className="validation-body">
        {lines.length > 0 ? (
          <ul className="bullets small">
            {lines.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        ) : (
          <p className="muted small">Nothing needed checking.</p>
        )}
        {report.issues.length > 0 ? (
          <ul className="issue-list small">
            {report.issues.map((issue, i) => (
              <li key={`${issue.module}-${i}`} className={issue.level === "warning" ? "warn" : "muted"}>
                <strong>{issue.module.replace(/_/g, " ")}:</strong> {issue.message}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </details>
  );
}
