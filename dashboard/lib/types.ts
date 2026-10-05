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

export interface RunManifest {
  run_id: string;
  started_at: string;
  finished_at: string;
  plans: string[];
  years: number[];
  jev: ApiUsage;
  llm: ApiUsage;
  counts: Record<string, number>;
}
