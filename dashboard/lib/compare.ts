import { formatMoney } from "@/lib/money";
import type { Run } from "@/lib/run-loader";
import type { ChangeCategory, Citation, Direction, ExtractedField, FieldChange, FieldValue, PlanDiff, RunManifest } from "@/lib/types";

// Turns diffs into what the Plan comparison and Changes pages show. Kept apart from the pages so it is easy to test.

/** The 15 v1 fields (SPEC decision 3), in the order a broker reads a Summary of Benefits. */
export const FIELDS: [name: string, label: string][] = [
  ["monthly_premium", "Monthly premium"],
  ["medical_deductible", "Medical deductible"],
  ["moop_in_network", "Maximum out-of-pocket (in network)"],
  ["pcp_copay", "Primary care visit"],
  ["specialist_copay", "Specialist visit"],
  ["emergency_room", "Emergency room"],
  ["urgent_care", "Urgent care"],
  ["inpatient_stay", "Inpatient hospital stay"],
  ["outpatient_surgery", "Outpatient surgery"],
  ["drug_deductible", "Drug deductible"],
  ["drug_tier_1", "Drug tier 1"],
  ["drug_tier_2", "Drug tier 2"],
  ["drug_tier_3", "Drug tier 3"],
  ["dental_allowance", "Dental allowance"],
  ["otc_allowance", "Over-the-counter allowance"],
];

export const fieldLabel = (name: string) => FIELDS.find(([key]) => key === name)?.[1] ?? name.replaceAll("_", " ");

export const CATEGORIES: [ChangeCategory, string][] = [
  ["premium", "Premium"],
  ["deductible", "Deductible"],
  ["moop", "Maximum out-of-pocket"],
  ["copays", "Copays"],
  ["drugs", "Drugs"],
  ["allowances", "Allowances"],
];

export const categoryLabel = (category: ChangeCategory) => CATEGORIES.find(([key]) => key === category)?.[1] ?? category;

export const DIRECTIONS: [Direction, string][] = [
  ["up", "Up"],
  ["down", "Down"],
  ["same", "No change"],
  ["added", "Added"],
  ["removed", "Removed"],
  ["not_comparable", "Not comparable"],
];

export const directionText = (direction: Direction) => DIRECTIONS.find(([key]) => key === direction)?.[1] ?? direction;

const UNITS: Record<string, string> = {
  per_month: "a month",
  per_year: "a year",
  per_quarter: "a quarter",
  per_visit: "a visit",
  per_day: "a day",
  per_stay: "a stay",
  per_prescription: "a prescription",
};

/** "$25.00 a month", "$45.00 copay a visit", "20% coinsurance a visit", "Not covered". Never a float. */
export function valueText(field: ExtractedField | null): string {
  if (field === null) return "Not found in the document";
  return fieldValueText(field.value, field.unit);
}

/** One value and its unit, for a PDF or CMS side that has no ExtractedField around it. */
export function fieldValueText(value: FieldValue | null, unitName: string | null | undefined): string {
  if (value === null) return "No value";
  const unit = unitName ? ` ${UNITS[unitName] ?? unitName.replaceAll("_", " ")}` : "";
  switch (value.kind) {
    case "money": return `${formatMoney(value.amount)}${unit}`;
    case "copay": return `${formatMoney(value.amount)} copay${unit}`;
    case "coinsurance": return `${value.percent}% coinsurance${unit}`;
    case "not_covered": return "Not covered";
  }
}

/** "H9999-001_2026_SB, page 1", or for a CMS row "CMS file crosswalk_2027.csv, row 1". */
export function citationText(citation: Citation): string {
  if (citation.method === "cms") return `CMS file ${citation.document_id}, row ${citation.page}`;
  return `${citation.document_id}, page ${citation.page}`;
}

/**
 * A page link only to the carrier's own copy named in the run manifest, and only over https.
 * Never a file from this repo: the dashboard does not serve carrier PDFs.
 */
export function carrierPageUrl(manifest: RunManifest, citation: Citation): string | null {
  if (citation.method === "cms") return null;
  const input = manifest.inputs.find((item) => item.kind === "pdf" && item.document_id === citation.document_id);
  return httpsPageUrl(input?.source_url, citation.page);
}

/** The recorded https URL with #page=N, or null for anything else (no URL, http, a path on this site). */
export function httpsPageUrl(source: string | null | undefined, page?: number): string | null {
  if (!source) return null;
  try {
    const url = new URL(source);
    if (url.protocol !== "https:") return null;
    if (page !== undefined) url.hash = `page=${page}`;
    return url.toString();
  } catch {
    return null;
  }
}

/**
 * Shown only below the floor, because only then does it change what a broker can quote. The floor
 * is the one the run used (manifest config), so it can never drift from the engine. At the floor is trusted.
 */
export function lowConfidence(field: ExtractedField | null, floor: number): string | null {
  if (field === null || field.confidence >= floor) return null;
  return `Read with confidence ${field.confidence}, below ${floor}`;
}

/** All 15 fields in order. A field the diff does not list was found in neither year. */
export function comparisonRows(diff: PlanDiff): { name: string; label: string; change: FieldChange | null }[] {
  return FIELDS.map(([name, label]) => ({ name, label, change: diff.changes.find((c) => c.field === name) ?? null }));
}

const REVIEW_KINDS: Record<string, string> = {
  shop_again_uncertain: "Cannot decide shop again",
  pdf_cms_mismatch: "PDF and CMS disagree",
  not_comparable: "Cannot be checked against CMS",
  conflicting_values: "Two values in one cell",
  not_extracted: "Not read from the document",
  crosswalk_row_missing: "No crosswalk row",
  unclassified_document: "Document not identified",
  rule_llm_disagree: "Rules and LLM disagree",
  unknown_period: "Unknown allowance period",
  unexpected_unit: "Unexpected period for a yearly amount",
};

export const reviewKindText = (kind: string) => REVIEW_KINDS[kind] ?? kind.replaceAll("_", " ");

export const diffFor = (run: Run, plan: string) => run.diffs.find((diff) => diff.old_plan_id === plan) ?? null;

export const planIds = (run: Run) => run.diffs.flatMap((diff) => (diff.old_plan_id ? [diff.old_plan_id] : []));

/** Counts per category and direction across every plan's changes, unchanged fields included. */
export function changeCounts(run: Run): Record<ChangeCategory, Record<Direction, number>> {
  const counts = Object.fromEntries(
    CATEGORIES.map(([category]) => [category, Object.fromEntries(DIRECTIONS.map(([d]) => [d, 0]))]),
  ) as Record<ChangeCategory, Record<Direction, number>>;
  for (const diff of run.diffs) for (const change of diff.changes) counts[change.category][change.direction] += 1;
  return counts;
}

export interface ChangeRow {
  plan: string;
  newPlan: string | null;
  change: FieldChange;
}

/** Every field that did not stay the same, plan by plan in field order. */
export function changedRows(run: Run): ChangeRow[] {
  return run.diffs.flatMap((diff) =>
    comparisonRows(diff).flatMap(({ change }) =>
      change && change.direction !== "same"
        ? [{ plan: diff.old_plan_id ?? "Unknown plan", newPlan: diff.new_plan_id, change }]
        : [],
    ),
  );
}
