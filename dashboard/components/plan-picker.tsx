import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { RunEyebrow } from "@/components/run-eyebrow";
import { planIds } from "@/lib/compare";
import type { Run } from "@/lib/run-loader";

// The nav's Plan comparison entry: pick a plan. `base` is the run's URL prefix.
export function PlanPicker({ run, base = "" }: { run: Run; base?: string }) {
  return (
    <div className="report-page">
      <header className="page-header">
        <RunEyebrow run={run} />
        <h1 className="page-title">Plan comparison: pick a plan</h1>
        <p className="page-context">Compare the 15 fields side by side, with the source page for each value.</p>
      </header>
      <ul aria-label="Available plans" className="plan-picker">
        {planIds(run).map((plan) => (
          <li key={plan}>
            <Link href={`${base}/plans/${plan}`} className="panel plan-picker-link">
              <span className="font-mono font-semibold underline">{plan}</span>
              <ArrowRight aria-hidden className="size-4" />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
