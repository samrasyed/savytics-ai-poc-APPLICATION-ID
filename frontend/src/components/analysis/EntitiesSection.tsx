import type { Entities, Entity } from "../../api/types";
import { Empty, Section } from "./ui";

const CATEGORIES: { key: keyof Entities; label: string }[] = [
  { key: "people", label: "People" },
  { key: "organizations", label: "Organizations" },
  { key: "dates", label: "Dates" },
  { key: "locations", label: "Locations" },
  { key: "technologies", label: "Technologies" },
  { key: "monetary_values", label: "Monetary values" },
  { key: "important_terms", label: "Important terms" },
];

// Renders one entity with its context and, for dates, the normalized date.
function EntityRow({ entity }: { entity: Entity }) {
  return (
    <li>
      <span className="entity-text">{entity.text}</span>
      {entity.normalized ? <span className="muted small"> · {entity.normalized}</span> : null}
      {entity.context ? <div className="muted small">{entity.context}</div> : null}
    </li>
  );
}

// Lists extracted names, dates, places, technologies, amounts and terms by category.
export default function EntitiesSection({ entities }: { entities: Entities }) {
  const filled = CATEGORIES.filter((c) => entities[c.key].length > 0);
  const total = CATEGORIES.reduce((sum, c) => sum + entities[c.key].length, 0);

  return (
    <Section title="Extracted entities" count={total} description="Names and values exactly as written in the document.">
      {filled.length === 0 ? (
        <Empty>No entities were found.</Empty>
      ) : (
        <div className="entity-grid">
          {filled.map((c) => (
            <div key={c.key} className="entity-group">
              <h3>
                {c.label} <span className="muted small">({entities[c.key].length})</span>
              </h3>
              <ul>
                {entities[c.key].map((e) => (
                  <EntityRow key={e.text} entity={e} />
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}
