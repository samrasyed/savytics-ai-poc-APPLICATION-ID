import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { AnalysisRecord } from "../api/types";
import AnalysisView from "./AnalysisView";
import fixture from "./__fixtures__/analysis.json";

const record = fixture as unknown as AnalysisRecord;

// Renders the analysis view to HTML for a record.
function render(r: AnalysisRecord): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <AnalysisView record={r} deleting={false} rerunning={false} onDelete={() => {}} onRerun={() => {}} />
    </MemoryRouter>,
  );
}

describe("AnalysisView", () => {
  // Checks every section appears in the required order.
  it("renders all sections in order", () => {
    const html = render(record);
    const order = [
      "Summary",
      "Key points",
      "Extracted entities",
      "Action items",
      "Decisions",
      "Contradictions",
      "Risks",
      "Dependencies",
      "Open questions",
    ];
    const positions = order.map((title) => html.indexOf(`<h2>${title}`));
    expect(positions.every((p) => p >= 0)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
    expect(html).not.toContain("<img");
  });

  // Checks missing owners and deadlines use the agreed wording.
  it("shows Unassigned and Not specified", () => {
    const html = render(record);
    expect(html).toContain("Unassigned");
    expect(html).toContain("Not specified");
    expect(html).toContain("Tentative");
    expect(html).toContain("AI-assessed");
  });

  // Checks the tab bar sits right under the title and opens on the overview of summary and key points.
  it("puts every section behind tabs under the title", () => {
    const html = render(record);
    const tabs = [...html.matchAll(/<button[^>]*role="tab"[^>]*>([\s\S]*?)<\/button>/g)].map((m) =>
      m[1].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim(),
    );
    expect(tabs.map((t) => t.replace(/ (\d+|!)$/, ""))).toEqual([
      "Overview",
      "Entities",
      "Action items",
      "Decisions",
      "Contradictions",
      "Risks",
      "Dependencies",
      "Open questions",
    ]);
    expect(html.indexOf("<h1>")).toBeLessThan(html.indexOf('role="tablist"'));
    expect(html.indexOf('role="tablist"')).toBeLessThan(html.indexOf("<h2>Summary"));
    expect(html).toMatch(/id="tab-overview"[^>]*aria-selected="true"/);
    expect(html.match(/aria-selected="true"/g)).toHaveLength(1);
    expect(html.match(/role="tabpanel"[^>]*hidden=""/g)).toHaveLength(7);
  });

  // Checks a failed check is flagged on its tab instead of showing a count.
  it("flags tabs whose check failed", () => {
    const failed: AnalysisRecord = {
      ...record,
      result: {
        ...record.result,
        intelligence: { ...record.result.intelligence, modules: { ...record.result.intelligence.modules, risks: "failed" } },
      },
    };
    expect(render(failed)).toMatch(/id="tab-risks"[\s\S]*?class="tab-flag"/);
  });

  // Checks an older analysis without intelligence data shows the not-run notice.
  it("handles analyses saved before the checks existed", () => {
    const old: AnalysisRecord = {
      ...record,
      result: {
        ...record.result,
        contradictions: [],
        risks: [],
        dependencies: [],
        intelligence: { status: "not_run", modules: {}, message: null, documents_compared: 0 },
      },
    };
    const html = render(old);
    expect(html).toContain("have not been run for this analysis");
    expect(html).toContain("Re-run checks");
  });
});
