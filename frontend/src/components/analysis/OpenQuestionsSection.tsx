import type { OpenQuestion, OpenQuestionCategory } from "../../api/types";
import { Empty, Section, Tag } from "./ui";

const CATEGORIES: { key: OpenQuestionCategory; label: string }[] = [
  { key: "missing_owner", label: "Missing task owners" },
  { key: "missing_deadline", label: "Missing deadlines" },
  { key: "unresolved_decision", label: "Unresolved decisions" },
  { key: "unclear_responsibility", label: "Unclear responsibilities" },
  { key: "missing_approval", label: "Missing approvals" },
  { key: "unanswered_question", label: "Unanswered questions" },
];

// Lists gaps in the document grouped by type, marking those found by automatic checks.
export default function OpenQuestionsSection({ questions }: { questions: OpenQuestion[] }) {
  const groups = CATEGORIES.map((c) => ({ ...c, items: questions.filter((q) => q.category === c.key) })).filter(
    (g) => g.items.length > 0,
  );

  return (
    <Section title="Open questions" count={questions.length}>
      {groups.length === 0 ? (
        <Empty>No open questions.</Empty>
      ) : (
        <div className="question-groups">
          {groups.map((g) => (
            <div key={g.key}>
              <h3>
                {g.label} <span className="muted small">({g.items.length})</span>
              </h3>
              <ul className="bullets">
                {g.items.map((q) => (
                  <li key={q.question}>
                    {q.question}{" "}
                    {q.origin === "check" ? (
                      <Tag title="Added by the validation checks, not by the AI.">Found by checks</Tag>
                    ) : null}
                    {q.evidence ? <div className="muted small">“{q.evidence}”</div> : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}
