import type { Dependency, ModuleState } from "../../api/types";
import { Empty, Evidence, Section } from "./ui";
import ModuleNotice from "./ModuleNotice";

// Lists task dependencies supported by the document, as a table.
export default function DependenciesSection({
  dependencies,
  state,
}: {
  dependencies: Dependency[];
  state: ModuleState | undefined;
}) {
  return (
    <Section
      title="Dependencies"
      count={dependencies.length}
      description="Only relationships the document states or clearly implies."
    >
      <ModuleNotice state={state} />
      {state === "ok" && dependencies.length === 0 ? <Empty>No dependencies were found.</Empty> : null}
      {dependencies.length > 0 ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Must happen first</th>
                <th>Waits for it</th>
                <th>Description</th>
                <th>Supporting evidence</th>
              </tr>
            </thead>
            <tbody>
              {dependencies.map((d) => (
                <tr key={`${d.source_task}->${d.dependent_task}`}>
                  <td className="strong">{d.source_task}</td>
                  <td className="strong">{d.dependent_task}</td>
                  <td>{d.description ?? <span className="muted">—</span>}</td>
                  <td>
                    <Evidence text={d.evidence} status={d.evidence_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </Section>
  );
}
