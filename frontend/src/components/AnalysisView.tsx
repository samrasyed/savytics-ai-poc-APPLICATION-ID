import { useRef, useState, type KeyboardEvent } from "react";
import {
  AlignLeft,
  CircleHelp,
  Gavel,
  GitCompareArrows,
  ListChecks,
  RotateCw,
  Tags,
  Target,
  Trash2,
  TriangleAlert,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import type { AnalysisRecord, IntelligenceStatus, ModuleState } from "../api/types";
import { formatDateTime, formatSeconds } from "../utils/format";
import ActionItemsSection from "./analysis/ActionItemsSection";
import ContradictionsSection from "./analysis/ContradictionsSection";
import DecisionsSection from "./analysis/DecisionsSection";
import DependenciesSection from "./analysis/DependenciesSection";
import EntitiesSection from "./analysis/EntitiesSection";
import OpenQuestionsSection from "./analysis/OpenQuestionsSection";
import RisksSection from "./analysis/RisksSection";
import ValidationNotes from "./analysis/ValidationNotes";
import { Empty } from "./analysis/ui";

interface Props {
  record: AnalysisRecord;
  deleting: boolean;
  rerunning: boolean;
  onDelete: () => void;
  onRerun: () => void;
}

type Tone = "butter" | "rose" | "mint" | "lavender" | "sky" | "peach";

interface TabDef {
  key: string;
  label: string;
  icon: LucideIcon;
  tone: Tone;
  count?: number;
  state?: ModuleState;
  panel: JSX.Element;
}

// Renders a list of strings, or a muted message when the list is empty.
function BulletList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <Empty>{empty}</Empty>;
  return (
    <ul className="bullets">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

// Explains when the intelligence checks are incomplete for this analysis.
function IntelligenceBanner({ status }: { status: IntelligenceStatus }) {
  if (status.status === "complete" || status.status === "disabled") return null;
  const text =
    status.status === "not_run"
      ? "Contradiction, risk and dependency checks have not been run for this analysis."
      : status.status === "partial"
        ? "Some checks could not be completed."
        : `The contradiction, risk and dependency checks could not be completed${status.message ? `: ${status.message}` : "."}`;
  return <div className="notice">{text} Use “Re-run checks” to try again.</div>;
}

// Renders one overview card (summary or key points) with its pastel icon tile.
function OverviewCard({
  title,
  icon: Icon,
  tone,
  count,
  children,
}: {
  title: string;
  icon: LucideIcon;
  tone: Tone;
  count?: number;
  children: JSX.Element;
}) {
  return (
    <section className={`card overview-card tone-${tone}`}>
      <div className="overview-head">
        <span className="tile" aria-hidden="true">
          <Icon size={18} strokeWidth={1.5} />
        </span>
        <h2>
          {title}
          {count !== undefined ? <span className="count-pill">{count}</span> : null}
        </h2>
      </div>
      {children}
    </section>
  );
}

// Builds the tab list: an overview (summary and key points) first, then each detail section,
// skipping the intelligence tabs when checks are off.
function buildTabs(record: AnalysisRecord): TabDef[] {
  const { result } = record;
  const modules = result.intelligence.modules;
  const intelligenceOff = result.intelligence.status === "disabled";
  const entityCount = Object.values(result.entities).reduce((sum, list) => sum + list.length, 0);

  const tabs: TabDef[] = [
    {
      key: "overview",
      label: "Overview",
      icon: AlignLeft,
      tone: "butter",
      panel: (
        <div className="overview">
          <OverviewCard title="Summary" icon={AlignLeft} tone="butter">
            <p className="summary">{result.summary}</p>
          </OverviewCard>
          <OverviewCard title="Key points" icon={Target} tone="rose" count={result.key_points.length}>
            <BulletList items={result.key_points} empty="No key points were found." />
          </OverviewCard>
        </div>
      ),
    },
    {
      key: "entities",
      label: "Entities",
      icon: Tags,
      tone: "sky",
      count: entityCount,
      panel: <EntitiesSection entities={result.entities} />,
    },
    {
      key: "actions",
      label: "Action items",
      icon: ListChecks,
      tone: "mint",
      count: result.action_items.length,
      panel: <ActionItemsSection items={result.action_items} />,
    },
    {
      key: "decisions",
      label: "Decisions",
      icon: Gavel,
      tone: "butter",
      count: result.decisions.length,
      panel: <DecisionsSection decisions={result.decisions} />,
    },
  ];

  if (!intelligenceOff) {
    tabs.push(
      {
        key: "contradictions",
        label: "Contradictions",
        icon: GitCompareArrows,
        tone: "peach",
        count: result.contradictions.length,
        state: modules.contradictions,
        panel: (
          <ContradictionsSection
            contradictions={result.contradictions}
            state={modules.contradictions}
            compared={result.intelligence.documents_compared}
          />
        ),
      },
      {
        key: "risks",
        label: "Risks",
        icon: TriangleAlert,
        tone: "rose",
        count: result.risks.length,
        state: modules.risks,
        panel: <RisksSection risks={result.risks} state={modules.risks} />,
      },
      {
        key: "dependencies",
        label: "Dependencies",
        icon: Workflow,
        tone: "lavender",
        count: result.dependencies.length,
        state: modules.dependencies,
        panel: <DependenciesSection dependencies={result.dependencies} state={modules.dependencies} />,
      },
    );
  }

  tabs.push({
    key: "questions",
    label: "Open questions",
    icon: CircleHelp,
    tone: "lavender",
    count: result.open_question_details.length,
    panel: <OpenQuestionsSection questions={result.open_question_details} />,
  });
  return tabs;
}

// Displays an analysis: title, then a sticky tab bar opening on the overview, one section at a time.
export default function AnalysisView({ record, deleting, rerunning, onDelete, onRerun }: Props) {
  const { result } = record;
  const intelligenceOff = result.intelligence.status === "disabled";
  const tabs = buildTabs(record);
  const [active, setActive] = useState(tabs[0].key);
  const current = tabs.some((t) => t.key === active) ? active : tabs[0].key;
  const barRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  // Opens a tab and, if the bar is stuck to the top, scrolls back to the start of the panel.
  function select(key: string, focus = false) {
    setActive(key);
    if (focus) tabRefs.current[key]?.focus();
    const bar = barRef.current;
    if (bar && bar.getBoundingClientRect().top <= 16) {
      const top = bar.getBoundingClientRect().top + window.scrollY - 12;
      window.scrollTo({ top, behavior: "smooth" });
    }
  }

  // Moves between tabs with the arrow, Home and End keys.
  function onTabKey(event: KeyboardEvent<HTMLButtonElement>) {
    const index = tabs.findIndex((t) => t.key === current);
    const moves: Record<string, number> = {
      ArrowRight: (index + 1) % tabs.length,
      ArrowLeft: (index - 1 + tabs.length) % tabs.length,
      Home: 0,
      End: tabs.length - 1,
    };
    if (!(event.key in moves)) return;
    event.preventDefault();
    select(tabs[moves[event.key]].key, true);
  }

  return (
    <article className="analysis">
      <header className="analysis-head poster">
        <div className="analysis-title">
          <p className="eyebrow">
            <span className="live-dot" aria-hidden="true" />
            Analysis
          </p>
          <h1>{record.title}</h1>
          <p className="meta">
            {formatDateTime(record.created_at)} · {record.model} · {formatSeconds(record.latency_ms)}
          </p>
        </div>
        <div className="head-actions">
          {!intelligenceOff ? (
            <button
              type="button"
              className="btn"
              onClick={onRerun}
              disabled={rerunning}
              title="Check again for contradictions, risks and dependencies, including against your latest documents"
            >
              <RotateCw size={15} strokeWidth={1.75} aria-hidden="true" className={rerunning ? "spin" : undefined} />
              {rerunning ? "Checking…" : "Re-run checks"}
            </button>
          ) : null}
          <button type="button" className="btn btn-danger" onClick={onDelete} disabled={deleting}>
            <Trash2 size={15} strokeWidth={1.75} aria-hidden="true" />
            {deleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </header>

      <div className="tabbar" ref={barRef}>
        <div className="tabs" role="tablist" aria-label="Analysis details">
          {tabs.map((tab) => {
            const selected = tab.key === current;
            const Icon = tab.icon;
            const flagged = tab.state !== undefined && tab.state !== "ok";
            return (
              <button
                key={tab.key}
                ref={(el) => {
                  tabRefs.current[tab.key] = el;
                }}
                type="button"
                role="tab"
                id={`tab-${tab.key}`}
                aria-selected={selected}
                aria-controls={`panel-${tab.key}`}
                tabIndex={selected ? 0 : -1}
                className={`tab tone-${tab.tone}${selected ? " is-active" : ""}`}
                onClick={() => select(tab.key)}
                onKeyDown={onTabKey}
                title={flagged ? "This check did not complete. Use “Re-run checks”." : undefined}
              >
                <span className="tile tile-sm" aria-hidden="true">
                  <Icon size={14} strokeWidth={1.75} />
                </span>
                <span className="tab-label">{tab.label}</span>
                {flagged ? (
                  <span className="tab-flag" aria-label="check incomplete">
                    !
                  </span>
                ) : tab.count !== undefined ? (
                  <span className="tab-count">{tab.count}</span>
                ) : null}
              </button>
            );
          })}
        </div>
      </div>

      <IntelligenceBanner status={result.intelligence} />

      {tabs.map((tab) => (
        <div
          key={tab.key}
          role="tabpanel"
          id={`panel-${tab.key}`}
          aria-labelledby={`tab-${tab.key}`}
          hidden={tab.key !== current}
          className="tab-panel"
        >
          {tab.panel}
        </div>
      ))}

      <ValidationNotes report={result.validation} />

      <details className="card source">
        <summary>Original text</summary>
        <pre>{record.input_text}</pre>
      </details>
    </article>
  );
}
