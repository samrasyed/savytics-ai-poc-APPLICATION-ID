export type Priority = "high" | "medium" | "low";
export type EvidenceStatus = "verified" | "partial" | "not_found" | "missing";
export type Basis = "fact" | "inference" | "assumption";
export type StatedOrInferred = "explicit" | "inferred";

export interface Entity {
  text: string;
  context: string | null;
  normalized: string | null;
}

export interface Entities {
  people: Entity[];
  organizations: Entity[];
  dates: Entity[];
  locations: Entity[];
  technologies: Entity[];
  monetary_values: Entity[];
  important_terms: Entity[];
}

export interface ActionItem {
  task: string;
  owner: string | null;
  owners: string[];
  due_date: string | null;
  deadline_type: "confirmed" | "tentative" | null;
  due_date_iso: string | null;
  status: "open" | "in_progress" | "done" | "blocked" | "unknown";
  priority: Priority | null;
  priority_source: StatedOrInferred | null;
  certainty: "high" | "medium" | "low";
  evidence: string | null;
  evidence_status: EvidenceStatus;
  basis: Basis | null;
}

export interface Decision {
  description: string;
  decision_maker: string | null;
  status: "confirmed" | "proposed" | "rejected" | "pending" | "changed";
  previous_decision: string | null;
  evidence: string | null;
  evidence_status: EvidenceStatus;
  basis: Basis | null;
}

export type OpenQuestionCategory =
  | "missing_deadline"
  | "missing_owner"
  | "unresolved_decision"
  | "unclear_responsibility"
  | "missing_approval"
  | "unanswered_question";

export interface OpenQuestion {
  question: string;
  category: OpenQuestionCategory;
  related_to: string | null;
  evidence: string | null;
  evidence_status: EvidenceStatus;
  origin: "document" | "check";
}

export interface ConflictValue {
  value: string;
  document_id: string | null;
  document_title: string | null;
  is_current: boolean;
  evidence: string | null;
  evidence_status: EvidenceStatus;
}

export interface Contradiction {
  description: string;
  conflict_type: "date" | "deadline" | "owner" | "decision" | "amount" | "scope" | "other";
  scope: "within_document" | "cross_document";
  values: ConflictValue[];
  resolution_status: "unresolved" | "resolved";
  suggested_action: string | null;
}

export interface Risk {
  description: string;
  category: "delay" | "resources" | "dependency" | "approval" | "technical" | "financial" | "other";
  severity: Priority;
  severity_source: StatedOrInferred;
  origin: StatedOrInferred;
  reason: string | null;
  evidence: string | null;
  evidence_status: EvidenceStatus;
  document_id: string | null;
  document_title: string | null;
  is_current: boolean;
  resolution_status: "unresolved" | "mitigated" | "resolved";
  mitigation: string | null;
  basis: Basis | null;
}

export interface Dependency {
  source_task: string;
  dependent_task: string;
  description: string | null;
  evidence: string | null;
  evidence_status: EvidenceStatus;
}

export interface ValidationIssue {
  level: "warning" | "info";
  module: string;
  message: string;
}

export interface ValidationReport {
  checks: Record<string, number>;
  issues: ValidationIssue[];
}

export type ModuleState = "ok" | "failed" | "not_run";

export interface IntelligenceStatus {
  status: "complete" | "partial" | "failed" | "disabled" | "not_run";
  modules: Record<string, ModuleState>;
  message: string | null;
  documents_compared: number;
}

export interface AnalysisResult {
  summary: string;
  key_points: string[];
  entities: Entities;
  action_items: ActionItem[];
  decisions: Decision[];
  open_questions: string[];
  open_question_details: OpenQuestion[];
  contradictions: Contradiction[];
  risks: Risk[];
  dependencies: Dependency[];
  validation: ValidationReport;
  intelligence: IntelligenceStatus;
}

export interface AnalysisRecord {
  id: string;
  title: string;
  input_text: string;
  result: AnalysisResult;
  provider: string;
  model: string;
  prompt_version: string;
  latency_ms: number;
  created_at: string;
}

export interface AnalysisListItem {
  id: string;
  title: string;
  created_at: string;
  summary_preview: string;
  action_item_count: number;
}

export interface AnalysisListResponse {
  items: AnalysisListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  provider: string;
  model: string;
  mock_mode: boolean;
  prompt_version: string;
  database: "ok" | "error";
  version: string;
}

export interface ErrorDetail {
  code: string;
  message: string;
  retryable: boolean;
  request_id: string;
  details: unknown;
}

export const MAX_TITLE_CHARS = 200;
export const MAX_TEXT_CHARS = 50_000;
