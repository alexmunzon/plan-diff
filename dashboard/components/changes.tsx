import Link from "next/link";

import { DirectionText, TABLE, TD, TH } from "@/components/change-parts";
import { RunEyebrow } from "@/components/run-eyebrow";
import { CARD } from "@/components/tiles";
import { CATEGORIES, DIRECTIONS, changeCounts, changedRows, fieldLabel, valueText } from "@/lib/compare";
import { plural } from "@/lib/overview";
import type { Run } from "@/lib/run-loader";
import { cn } from "@/lib/utils";

// A dense table, not a chart: the dashboard has no chart library and 6 by 6 counts read fine as numbers.
export function Changes({ run, base = "" }: { run: Run; base?: string }) {
  const counts = changeCounts(run);
  const rows = changedRows(run);
  const { years } = run.manifest;
  return (
    <div className="report-page">
      <header className="page-header">
        <RunEyebrow run={run} />
        <h1 className="page-title">Where are costs moving across plans?</h1>
        <p className="page-context tabular-nums">
          Plan years {years.join(" to ")}, {plural(run.diffs.length, "plan")}, run {run.manifest.run_id}. Each
          field of each plan is counted once.
        </p>
      </header>
      <section aria-labelledby="counts-heading" tabIndex={0} className={cn(CARD, "overflow-x-auto")}>
        <h2 id="counts-heading" className="panel-title">Fields by category and direction</h2>
        <table aria-labelledby="counts-heading" className={cn(TABLE, "min-w-[640px]")}>
          <thead>
            <tr>
              <th scope="col" className={TH}>Category</th>
              {DIRECTIONS.map(([direction]) => (
                <th key={direction} scope="col" className={cn(TH, "text-right")}><DirectionText direction={direction} /></th>
              ))}
            </tr>
          </thead>
          <tbody>
            {CATEGORIES.map(([category, label]) => (
              <tr key={category} aria-label={label}>
                <th scope="row" className={cn(TD, "font-medium")}>{label}</th>
                {DIRECTIONS.map(([direction]) => (
                  <td key={direction} className={cn(TD, "text-right", counts[category][direction] === 0 && "table-zero")}>
                    {counts[category][direction]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section aria-labelledby="list-heading" tabIndex={0} className={cn(CARD, "overflow-x-auto")}>
        <h2 id="list-heading" className="panel-title">
          Changes and values needing review ({plural(rows.length, "field")})
        </h2>
        {rows.length === 0 ? (
          <p className="p-3 text-sm">No changes or values needing review.</p>
        ) : (
          <table aria-labelledby="list-heading" className={cn(TABLE, "min-w-[720px]")}>
            <thead>
              <tr>
                <th scope="col" className={TH}>Plan</th>
                <th scope="col" className={TH}>Field</th>
                <th scope="col" className={TH}>{years[0]}</th>
                <th scope="col" className={TH}>{years[years.length - 1]}</th>
                <th scope="col" className={TH}>Direction</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ plan, newPlan, change }) => (
                <tr key={`${plan} ${change.field}`} aria-label={`${plan} ${fieldLabel(change.field)}`}>
                  <td className={TD}>
                    <Link href={`${base}/plans/${plan}`} className="font-mono underline">{plan}</Link>
                    {newPlan && newPlan !== plan && (
                      <span className="block text-xs muted">now {newPlan}</span>
                    )}
                  </td>
                  <td className={TD}>{fieldLabel(change.field)}</td>
                  <td className={TD}>{valueText(change.old)}</td>
                  <td className={TD}>{valueText(change.new)}</td>
                  <td className={TD}><DirectionText direction={change.direction} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
