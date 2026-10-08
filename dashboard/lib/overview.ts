import type { Run } from "@/lib/run-loader";
import type { PlanDiff } from "@/lib/types";

// Turns a run into what the Overview shows. Kept apart from the page so it is easy to test.

/** Review signals retain the recorded flag; they do not decide client suitability. */
export function reviewFlagText(value: boolean | null): string {
  if (value === null) return "Undecided, needs review";
  return value ? "Flagged for review" : "No change flag";
}

const ORDER = (value: boolean | null) => (value === true ? 0 : value === null ? 1 : 2);

export function crosswalkText(diff: PlanDiff): string {
  const next = diff.new_plan_id ?? "no plan";
  switch (diff.crosswalk_status) {
    case null: return "No crosswalk row";
    case "new": return "New plan";
    case "continuing": return `Renews as ${next}`;
    case "consolidated": return `Consolidated into ${next}`;
    case "service_area_reduced": return `Renews as ${next}, smaller service area`;
    case "service_area_expanded": return `Renews as ${next}, larger service area`;
    case "terminated": return "Terminated";
  }
}

export interface OverviewRow {
  planId: string;
  shopAgain: boolean | null;
  reasons: string[];
  /** For an undecided plan: why it could not be decided (its high review items). */
  undecidedBecause: string[];
  crosswalk: string;
  reviewCount: number;
}

export function overviewRows(run: Run): OverviewRow[] {
  const rows = run.diffs.map((diff) => {
    const planId = diff.old_plan_id ?? diff.new_plan_id ?? "Unknown plan";
    return {
      planId,
      shopAgain: diff.shop_again,
      reasons: diff.reasons,
      undecidedBecause:
        diff.shop_again === null ? diff.review.filter((r) => r.severity === "high").map((r) => r.reason) : [],
      crosswalk: crosswalkText(diff),
      // Counted by the plan's own (old) id, so a consolidated plan does not repeat its new plan's items.
      reviewCount: run.reviewQueue.filter((item) => item.plan_id === planId).length,
    };
  });
  return rows.sort((a, b) => ORDER(a.shopAgain) - ORDER(b.shopAgain));
}

export function plural(count: number, word: string): string {
  return `${count.toLocaleString("en-US")} ${word}${count === 1 ? "" : "s"}`;
}

export function summary(run: Run) {
  const totals = run.accuracy.rows.filter((row) => row.field === null);
  const matched = totals.reduce((sum, row) => sum + row.matched, 0);
  const mismatched = totals.reduce((sum, row) => sum + row.mismatched, 0);
  const checked = matched + mismatched;
  const notComparable = totals.reduce((sum, row) => sum + (row.not_comparable ?? 0), 0);
  const notExtracted = totals.reduce((sum, row) => sum + row.not_extracted, 0);
  const { plans, as_of } = run.accuracy;
  // The run says what it read (`plan-diff run --data-kind`); plan ids are never used to guess.
  const synthetic = run.manifest.data_kind === "synthetic";
  const slice = `${synthetic ? "on synthetic fixtures" : `across ${plural(plans.length, "public plan")}`}${as_of ? `, as of ${as_of}` : ""}`;
  const accuracyCaveat = synthetic
    ? "Synthetic test fixtures; not production accuracy."
    : `Extraction rules were tuned on these same documents, not held-out measured accuracy. ${plural(notComparable, "value")} not comparable and ${plural(notExtracted, "value")} not extracted.`;
  return {
    compared: run.diffs.length,
    flagged: run.diffs.filter((diff) => diff.shop_again === true).length,
    undecided: run.diffs.filter((diff) => diff.shop_again === null).length,
    reviewItems: run.reviewQueue.length,
    matchRate: checked === 0 ? "None checked" : `${((100 * matched) / checked).toFixed(1)}%`,
    matchContext: `${matched} of ${checked} comparable values, ${slice}. ${accuracyCaveat}`,
  };
}
