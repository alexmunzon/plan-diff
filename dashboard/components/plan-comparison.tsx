import { CitationText, DirectionText, TABLE, TD, TH, ValueCell } from "@/components/change-parts";
import { ANSWER_TONE } from "@/components/overview";
import { SeverityBadge } from "@/components/severity-badge";
import { CARD } from "@/components/tiles";
import { categoryLabel, comparisonRows, fieldLabel, reviewKindText } from "@/lib/compare";
import { crosswalkText, shopAgainText } from "@/lib/overview";
import type { Run } from "@/lib/run-loader";
import type { PlanDiff } from "@/lib/types";
import { cn } from "@/lib/utils";

const SEVERITY_TONE = { high: "error", medium: "warning", low: "info" } as const;
const sentence = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

function Verdict({ diff, run }: { diff: PlanDiff; run: Run }) {
  const undecided = diff.shop_again === null;
  const lines = undecided ? diff.review.filter((r) => r.severity === "high").map((r) => r.reason) : diff.reasons;
  return (
    <section aria-label="Verdict" className={cn(CARD, "grid gap-3 p-4 sm:grid-cols-2")}>
      <div className="space-y-1 text-sm">
        <p className="text-xs text-slate-600 dark:text-slate-400">Crosswalk</p>
        <p className="font-medium">{crosswalkText(diff)}</p>
        {diff.evidence.map((citation, i) => (
          <p key={i}>
            <CitationText citation={citation} manifest={run.manifest} />
            {citation.text && <span className="text-xs text-slate-600 dark:text-slate-400">: {citation.text}</span>}
          </p>
        ))}
      </div>
      <div className="space-y-1 text-sm">
        <p className="text-xs text-slate-600 dark:text-slate-400">
          Shop again: <SeverityBadge tone={ANSWER_TONE(diff.shop_again)} label={shopAgainText(diff.shop_again)} />
        </p>
        <p className="text-xs text-slate-600 dark:text-slate-400">{undecided ? "Why it is undecided" : "Why"}</p>
        {lines.length === 0 ? (
          <p>No change crossed a shop-again threshold.</p>
        ) : (
          <ul className="list-disc pl-4">
            {lines.map((line) => <li key={line}>{sentence(line)}</li>)}
          </ul>
        )}
      </div>
    </section>
  );
}

export function PlanComparison({ run, diff }: { run: Run; diff: PlanDiff }) {
  const plan = diff.old_plan_id ?? "Unknown plan";
  const { old_year: oldYear, new_year: newYear } = diff;
  const review = run.reviewQueue.filter((item) => item.plan_id === plan);
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">
          What exactly changed between {oldYear} and {newYear} for this plan?
        </h1>
        <p className="mt-1 font-mono text-sm text-slate-600 dark:text-slate-400">{plan}</p>
      </header>
      <Verdict diff={diff} run={run} />
      <section aria-labelledby="fields-heading" className={cn(CARD, "overflow-x-auto")}>
        <h2 id="fields-heading" className="px-3 pt-3 text-sm font-semibold">The 15 fields, side by side</h2>
        {diff.changes.length === 0 ? (
          <p className="p-3 text-sm">
            {diff.crosswalk_status === "terminated"
              ? `No ${newYear} plan to compare: the plan is terminated.`
              : "Nothing to compare: the plan was not diffed. See the review items below."}
          </p>
        ) : (
          <table className={cn(TABLE, "min-w-[720px]")}>
            <thead>
              <tr>
                <th className={TH}>Field</th>
                <th className={TH}>{oldYear}</th>
                <th className={TH}>{newYear}</th>
                <th className={TH}>Change</th>
                <th className={TH}>Category</th>
              </tr>
            </thead>
            <tbody>
              {comparisonRows(diff).map(({ name, label, change }) => (
                <tr key={name} aria-label={label}>
                  <th scope="row" className={cn(TD, "font-medium")}>{label}</th>
                  <td className={TD}><ValueCell field={change?.old ?? null} manifest={run.manifest} /></td>
                  <td className={TD}><ValueCell field={change?.new ?? null} manifest={run.manifest} /></td>
                  <td className={TD}>{change ? <DirectionText direction={change.direction} /> : "Not found in either year"}</td>
                  <td className={TD}>{change ? categoryLabel(change.category) : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <section aria-labelledby="review-heading" className={cn(CARD, "p-3")}>
        <h2 id="review-heading" className="text-sm font-semibold">Review items for this plan</h2>
        {review.length === 0 ? (
          <p className="mt-1 text-sm">No review items.</p>
        ) : (
          <ul className="mt-2 space-y-2 text-sm">
            {review.map((item, i) => (
              <li key={i} className="space-y-0.5">
                <p className="flex flex-wrap items-center gap-2">
                  <SeverityBadge tone={SEVERITY_TONE[item.severity]} label={sentence(item.severity)} />
                  <span className="font-medium">{reviewKindText(item.kind)}</span>
                  <span className="text-xs text-slate-600 tabular-nums dark:text-slate-400">
                    {[item.field && fieldLabel(item.field), item.year].filter(Boolean).join(", ")}
                  </span>
                </p>
                <p>{sentence(item.reason)}</p>
                <p className="flex flex-wrap gap-x-3">
                  {item.evidence.map((citation, j) => <CitationText key={j} citation={citation} manifest={run.manifest} />)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
