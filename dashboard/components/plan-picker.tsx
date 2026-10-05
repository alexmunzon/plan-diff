import Link from "next/link";

import { planIds } from "@/lib/compare";
import type { Run } from "@/lib/run-loader";

// The nav's Plan comparison entry: pick a plan. PR 15: `base` is the run's URL prefix.
export function PlanPicker({ run, base = "" }: { run: Run; base?: string }) {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Plan comparison: pick a plan</h1>
      <ul className="space-y-1 text-sm">
        {planIds(run).map((plan) => (
          <li key={plan}>
            <Link href={`${base}/plans/${plan}`} className="font-mono underline">{plan}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
