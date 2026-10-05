import Link from "next/link";

import { SeverityBadge, type Tone } from "@/components/severity-badge";
import { CARD, Tile } from "@/components/tiles";
import { formatMoney } from "@/lib/money";
import { overviewRows, plural, shopAgainText, summary, type OverviewRow } from "@/lib/overview";
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
    <li aria-label={`Plan ${row.planId}`} className={cn(CARD, "grid gap-2 p-4 sm:grid-cols-[13rem_1fr_15rem] sm:gap-4")}>
      <div className="space-y-1">
        <Link href={`${base}/plans/${row.planId}`} className="font-mono text-sm font-medium underline">{row.planId}</Link>
        <p className="text-xs text-slate-600 dark:text-slate-400">
          Shop again: <SeverityBadge tone={ANSWER_TONE(row.shopAgain)} label={shopAgainText(row.shopAgain)} />
        </p>
      </div>
      <div className="text-sm">
        <p className="text-xs text-slate-600 dark:text-slate-400">
          {row.shopAgain === null && row.reasons.length === 0 ? "Why it is undecided" : "Why"}
        </p>
        {lines.length === 0 ? (
          <p>No change crossed a shop-again threshold.</p>
        ) : (
          <ul className="list-disc pl-4">
            {lines.map((line) => <li key={line}>{line}</li>)}
          </ul>
        )}
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-2 text-xs tabular-nums sm:text-right">
        <dt className="text-slate-600 dark:text-slate-400">Crosswalk</dt>
        <dd>{row.crosswalk}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Review</dt>
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
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Which plans changed enough that a client should shop again?</h1>
        <p className="mt-1 text-sm text-slate-600 tabular-nums dark:text-slate-400">
          Plan years {manifest.years.join(" to ")}, run {manifest.run_id}. Flagged plans come first.
        </p>
      </header>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Tile label="Plans compared" value={String(totals.compared)} context={`${manifest.years.join(" vs ")}, by CMS crosswalk`} />
        <Tile label="Shop again" tone="error" value={String(totals.flagged)} context="Plans flagged with reasons" />
        <Tile label="Undecided" tone="warning" value={String(totals.undecided)} context="Need a person to review" />
        <Tile label="Review items" tone="info" value={String(totals.reviewItems)} context="Open in the review queue" />
        <div className="col-span-2 lg:col-span-1">
          <Tile label="Accuracy match rate" value={totals.matchRate} context={totals.matchContext} />
        </div>
      </div>
      <section aria-labelledby="plans-heading">
        <h2 id="plans-heading" className="sr-only">Plans</h2>
        <ul className="space-y-3">
          {rows.map((row) => <PlanRow key={row.planId} row={row} base={base} />)}
        </ul>
      </section>
      <p className="text-xs text-slate-600 tabular-nums dark:text-slate-400">
        {usageText("Jev", manifest.jev)}. {usageText("LLM", manifest.llm)}. {manifest.data_kind === "synthetic" ? "Synthetic test fixtures." : "Public Texas carrier documents and CMS files."}
      </p>
    </div>
  );
}
