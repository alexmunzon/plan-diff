import { notFound } from "next/navigation";

import { PlanComparison } from "@/components/plan-comparison";
import { diffFor, planIds } from "@/lib/compare";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";

// One static page per plan in the committed demo run, built at build time. Any other id is a 404.
export const dynamicParams = false;

export async function generateStaticParams() {
  return planIds(await loadRunDir(DEMO_RUN_DIR)).map((plan) => ({ plan }));
}

export default async function PlanPage({ params }: PageProps<"/plans/[plan]">) {
  const { plan } = await params;
  const run = await loadRunDir(DEMO_RUN_DIR);
  const diff = diffFor(run, plan);
  if (!diff) notFound();
  return <PlanComparison run={run} diff={diff} />;
}
