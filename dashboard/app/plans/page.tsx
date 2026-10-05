import Link from "next/link";

import { planIds } from "@/lib/compare";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";

// The nav's Plan comparison entry: pick a plan.
export default async function PlansPage() {
  const run = await loadRunDir(DEMO_RUN_DIR);
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Plan comparison: pick a plan</h1>
      <ul className="space-y-1 text-sm">
        {planIds(run).map((plan) => (
          <li key={plan}>
            <Link href={`/plans/${plan}`} className="font-mono underline">{plan}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
