// Mirrors the engine's JSON Schema (`plan-diff schema export`, models in engine/src/plan_diff/models/).
// Only the parts the dashboard reads. Money and percents stay decimal text, never numbers.

export type CrosswalkStatus =
  | "new" | "continuing" | "consolidated" | "service_area_reduced" | "service_area_expanded" | "terminated";
export type Severity = "low" | "medium" | "high";
export type ChangeCategory = "premium" | "deductible" | "moop" | "copays" | "drugs" | "allowances";
export type Direction = "up" | "down" | "same" | "added" | "removed" | "not_comparable";

export interface Citation {
  document_id: string;
  page: number;
  method: "rule" | "llm" | "cms" | "human";
  text?: string | null;
}

export type FieldValue =
  | { kind: "money"; amount: string }
  | { kind: "copay"; amount: string }
  | { kind: "coinsurance"; percent: string }
  | { kind: "not_covered" };

export interface ExtractedField {
  name: string;
  value: FieldValue;
  unit: string | null;
  citation: Citation;
  confidence: number;
}

export interface FieldChange {
  field: string;
  old: ExtractedField | null;
  new: ExtractedField | null;
  category: ChangeCategory;
  direction: Direction;
}

export interface ReviewItem {
  kind: string;
  plan_id: string | null;
  year: number | null;
  field: string | null;
  evidence: Citation[];
  reason: string;
  severity: Severity;
  confidence?: number | null;
}

export interface PlanDiff {
  old_plan_id: string | null;
  new_plan_id: string | null;
  old_year: number;
  new_year: number;
  crosswalk_status: CrosswalkStatus | null;
  changes: FieldChange[];
  /** true: shop again. false: no. null: undecided, needs review (never "no"). */
  shop_again: boolean | null;
  reasons: string[];
  evidence: Citation[];
  review: ReviewItem[];
}

export interface AccuracyRow {
  field: string | null;
  method: Citation["method"];
  matched: number;
  mismatched: number;
  not_extracted: number;
  not_in_cms: number;
  match_rate: number | null;
  not_comparable?: number;
}

export interface AccuracyTable {
  rows: AccuracyRow[];
  plans: string[];
  years: number[];
  run_id: string | null;
  as_of: string | null;
}

export interface ApiUsage {
  mode: "off" | "replay" | "record" | "live";
  calls: number;
  cost_usd: string;
}

/** One input file. `source_url` is the carrier's own https copy, set only for fetched PDFs (PR 14). */
export interface RunInput {
  kind: "pdf" | "cms";
  path: string;
  sha256: string;
  status: "classified" | "unsure" | "unreadable" | "outside_slice" | null;
  document_id: string | null;
  plan_id: string | null;
  year: number | null;
  document_type: string | null;
  source_url?: string | null;
  page_count?: number | null;
}

/** The decision values the run used (PR 14). The dashboard never keeps its own copy. */
export interface RunConfig {
  confidence_floor: number;
  premium_up: string;
  moop_up: string;
  drug_deductible_up: string;
}

export interface ValidationResult {
  plan_id: string;
  year: number;
  field: string;
  pdf_value: FieldValue | null;
  cms_value: FieldValue | null;
  verdict: "match" | "mismatch" | "not_in_cms" | "not_extracted" | "not_comparable";
  pdf_citation: Citation | null;
  cms_citation: Citation | null;
  pdf_unit?: string | null;
  cms_unit?: string | null;
  reason?: string | null;
}

export interface PlanRecord {
  plan_id: string;
  year: number;
  carrier: string;
  plan_name: string;
  fields: Record<string, ExtractedField>;
  documents: string[];
}

export interface RunManifest {
  run_id: string;
  /** Set by `plan-diff run --data-kind`. Never guessed from plan ids. */
  data_kind: "synthetic" | "public";
  started_at: string;
  finished_at: string;
  plans: string[];
  years: number[];
  inputs: RunInput[];
  jev: ApiUsage;
  llm: ApiUsage;
  counts: Record<string, number>;
  config: RunConfig;
}
