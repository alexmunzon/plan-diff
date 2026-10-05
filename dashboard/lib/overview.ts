import type { Run } from "@/lib/run-loader";
import type { PlanDiff } from "@/lib/types";

// Turns a run into what the Overview shows. Kept apart from the page so it is easy to test.

/** Undecided is its own answer. It is never shown as "No". */
export function shopAgainText(value: boolean | null): string {
  if (value === null) return "Undecided, needs review";
  return value ? "Yes" : "No";
}

const ORDER = (value: boolean | null) => (value === true ? 0 : value === null ? 1 : 2);

const sentence = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

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
      reasons: diff.reasons.map(sentence),
      undecidedBecause:
        diff.shop_again === null ? diff.review.filter((r) => r.severity === "high").map((r) => sentence(r.reason)) : [],
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
  const checked = matched + totals.reduce((sum, row) => sum + row.mismatched, 0);
  const { plans, as_of } = run.accuracy;
  // H9999 is the made-up contract number every synthetic fixture uses.
  const synthetic = plans.length > 0 && plans.every((plan) => plan.startsWith("H9999-"));
  const slice = `${synthetic ? "on synthetic fixtures" : `on ${plural(plans.length, "plan")}`}${as_of ? `, as of ${as_of}` : ""}`;
  return {
    compared: run.diffs.length,
    flagged: run.diffs.filter((diff) => diff.shop_again === true).length,
    undecided: run.diffs.filter((diff) => diff.shop_again === null).length,
    reviewItems: run.reviewQueue.length,
    matchRate: checked === 0 ? "None checked" : `${((100 * matched) / checked).toFixed(1)}%`,
    matchContext: `${matched} of ${checked} checked values, ${slice}`,
  };
}
