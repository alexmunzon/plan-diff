import { PlanPicker } from "@/components/plan-picker";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";

export default async function PlansPage() {
  return <PlanPicker run={await loadRunDir(DEMO_RUN_DIR)} />;
}
