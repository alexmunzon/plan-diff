import { FIELDS, fieldLabel, httpsPageUrl } from "@/lib/compare";
import type { Run } from "@/lib/run-loader";
import type { AccuracyRow, ReviewItem, RunInput, Severity } from "@/lib/types";

// What the Trust and Documents pages show. Kept apart from the pages so it is easy to test.

export const dataKindText = (run: Run) =>
  run.manifest.data_kind === "synthetic" ? "Synthetic test fixtures" : "Public carrier documents and CMS files";

/** The slice and date every accuracy number carries, so it is never quoted unlabeled. */
export function sliceText(run: Run): string {
  const { plans, years } = run.accuracy.plans.length ? run.accuracy : run.manifest;
  return `Plans ${plans.join(", ")}; plan years ${years.join(" and ")}`;
}

export const asOf = (run: Run) => run.accuracy.as_of ?? run.manifest.started_at.slice(0, 10);

/** Matched over matched plus mismatched. Not comparable, not extracted, and not in CMS are left out. */
export function matchRateText(row: AccuracyRow): string {
  const comparable = row.matched + row.mismatched;
  if (comparable === 0) return "No comparable values";
  const tenths = Math.round((row.matched * 1000) / comparable) / 10;
  return `${tenths}% (${row.matched} of ${comparable})`;
}

export const methodText = (method: AccuracyRow["method"]) =>
  ({ rule: "Rules", llm: "LLM", cms: "CMS", human: "Person" })[method] ?? method;

export const accuracyLabel = (row: AccuracyRow) => `${row.field ? fieldLabel(row.field) : "All fields"}, ${methodText(row.method)}`;

/** Plain-language meaning of each review kind, shown once per group. */
export const REVIEW_EXPLANATIONS: Record<string, string> = {
  shop_again_uncertain:
    "A value that can decide shop again is missing, unclear, read with low confidence, or disagrees with CMS, so the answer is left undecided instead of guessed.",
  pdf_cms_mismatch:
    "The carrier document and the CMS file give different values. Both are shown and neither is picked. Check the page before quoting.",
  not_comparable:
    "The document and CMS state this value for different periods or units, so the two cannot be checked against each other.",
  conflicting_values: "One cell held two or more values. The first was kept at lower confidence; read the page to confirm.",
  not_extracted: "The rules could not read this value from the document.",
  crosswalk_row_missing: "CMS has no crosswalk row for this plan, so it is not treated as terminated.",
  unclassified_document: "The document's plan, year, or type could not be identified, so none of its values were used.",
  rule_llm_disagree: "The rules and the LLM read different values. The rule value is kept and a person should check.",
  unknown_period: "An allowance states a period the tool does not know, so it was not turned into a yearly amount.",
  unexpected_unit: "A yearly amount's cell states another period, so it is held at low confidence.",
};

const SEVERITY_ORDER: Severity[] = ["high", "medium", "low"];

/** The queue by severity (high first), then by kind in first-seen order. Empty groups are dropped. */
export function reviewGroups(queue: ReviewItem[]) {
  return SEVERITY_ORDER.map((severity) => {
    const items = queue.filter((item) => item.severity === severity);
    const kinds = [...new Set(items.map((item) => item.kind))];
    return { severity, count: items.length, kinds: kinds.map((kind) => ({ kind, items: items.filter((i) => i.kind === kind) })) };
  }).filter((group) => group.count > 0);
}

const STATUS: Record<string, string> = {
  unsure: "Not identified, in the review queue; no values used",
  unreadable: "Could not be opened, in the review queue; no values used",
  outside_slice: "Outside this run's plans and years; no values used",
};

export interface DocumentRow {
  input: RunInput;
  id: string;
  carrier: string;
  plan: string;
  year: number | null;
  status: string | null;
  /** The carrier's own https URL as recorded in the run, or null. Never a file from this repo. */
  url: string | null;
  values: { field: string; label: string; page: number }[];
}

/** Every PDF the run read, with each value cited from it in field order. */
export function documentRows(run: Run): DocumentRow[] {
  return run.manifest.inputs
    .filter((input) => input.kind === "pdf")
    .map((input) => {
      const id = input.document_id ?? input.path;
      const records = run.plans.filter((plan) => plan.documents.includes(id));
      const values = FIELDS.flatMap(([field, label]) =>
        records.flatMap((record) => {
          const cited = record.fields[field];
          return cited && cited.citation.document_id === id ? [{ field, label, page: cited.citation.page }] : [];
        }),
      );
      const record = records[0];
      return {
        input,
        id,
        carrier: record?.carrier ?? "Not identified",
        plan: input.plan_id ? `${input.plan_id}${record ? `, ${record.plan_name}` : ""}` : "Not identified",
        year: input.year,
        status: STATUS[input.status ?? ""] ?? null,
        url: httpsPageUrl(input.source_url),
        values,
      };
    });
}

/** Said in place of a link when the run recorded no carrier URL for a document. */
export const noLinkText = (run: Run) =>
  run.manifest.data_kind === "synthetic"
    ? "Synthetic test document, generated by the demo; not stored in the repo"
    : "No carrier link recorded for this file; it is not stored in the repo";
