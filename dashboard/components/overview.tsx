import Link from "next/link";

import { SeverityBadge, type Tone } from "@/components/severity-badge";
import { RunEyebrow } from "@/components/run-eyebrow";
import { CARD, Tile } from "@/components/tiles";
import { formatMoney } from "@/lib/money";
import { overviewRows, plural, reviewFlagText, summary, type OverviewRow } from "@/lib/overview";
import type { Run } from "@/lib/run-loader";
import type { ApiUsage } from "@/lib/types";
import { cn } from "@/lib/utils";

// Color is never the only signal: each answer is a word plus an icon.
export const ANSWER_TONE = (value: boolean | null): Tone => (value === null ? "warning" : value ? "error" : "pass");

function usageText(name: string, usage: ApiUsage): string {
  return `${name} ${usage.mode}, ${plural(usage.calls, "call")}, ${formatMoney(usage.cost_usd)}`;
}

function PlanRow({ row, base }: { row: OverviewRow; base: string }) {
  const lines = row.reasons.length > 0 ? row.reasons : row.undecidedBecause;
  return (
    <li aria-label={`Plan ${row.planId}`} className="plan-row">
      <div className="space-y-1">
        <Link href={`${base}/plans/${row.planId}`} className="plan-id font-mono text-sm underline">{row.planId}</Link>
        <p className="text-xs muted">
          <SeverityBadge tone={ANSWER_TONE(row.shopAgain)} label={reviewFlagText(row.shopAgain)} />
        </p>
      </div>
      <div className="text-sm">
        <p className="reason-label muted">
          {row.shopAgain === null && row.reasons.length === 0 ? "Why it is undecided" : "Why"}
        </p>
        {lines.length === 0 ? (
          <p>No change crossed a review threshold.</p>
        ) : (
          <ul className="list-disc pl-4">
            {lines.map((line) => <li key={line}>{line}</li>)}
          </ul>
        )}
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-2 text-xs tabular-nums sm:text-right">
        <dt className="muted">Crosswalk</dt>
        <dd>{row.crosswalk}</dd>
        <dt className="muted">Review</dt>
        <dd>{row.reviewCount === 0 ? "No review items" : plural(row.reviewCount, "review item")}</dd>
      </dl>
    </li>
  );
}

/** `base` is the run's URL prefix (PR 15): "" for the demo, "/texas" for the real run. */
export function Overview({ run, base = "" }: { run: Run; base?: string }) {
  const totals = summary(run);
  const rows = overviewRows(run);
  const { manifest } = run;
  return (
    <div className="report-page">
      <header className="page-header">
        <RunEyebrow run={run} />
        <h1 className="page-title">Which plan changes need broker review?</h1>
        <p className="page-context">
          Compare cited changes and check unresolved evidence before broker review. Flags are not suitability recommendations.
        </p>
        <p className="page-context tabular-nums">
          Plan years {manifest.years.join(" to ")}, run {manifest.run_id}. Flagged plans come first.
        </p>
        <div className="page-actions">
          <Link href={`${base}/plans`} className="action-link action-primary">Compare plan changes</Link>
          <Link href={`${base}/trust#queue-heading`} className="action-link">Review evidence</Link>
        </div>
      </header>
      <div className="metric-grid">
        <Tile label="Plans compared" value={String(totals.compared)} context={`${manifest.years.join(" vs ")}, by CMS crosswalk`} />
        <Tile label="Flagged for review" tone="error" value={String(totals.flagged)} context="Plans with a change flag and reasons" />
        <Tile label="Undecided" tone="warning" value={String(totals.undecided)} context="Need a person to review" />
        <Tile label="Review items" tone="info" value={String(totals.reviewItems)} context="Open in the review queue" />
      </div>
      <section aria-labelledby="plans-heading">
        <h2 id="plans-heading" className="section-heading">Plans</h2>
        <ul className={cn(CARD, "plan-list")}>
          {rows.map((row) => <PlanRow key={row.planId} row={row} base={base} />)}
        </ul>
      </section>
      <details className="technical-details">
        <summary>Run technical details</summary>
        <div className="accuracy-summary">
          <Tile label="Accuracy match rate" value={totals.matchRate} context={totals.matchContext} />
        </div>
        <p className="report-footer tabular-nums">
          {usageText("Jev", manifest.jev)}. {usageText("LLM", manifest.llm)}. {manifest.data_kind === "synthetic" ? "Synthetic test fixtures." : "Public Texas carrier documents and CMS files."}
        </p>
      </details>
    </div>
  );
}
