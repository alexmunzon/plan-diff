import { PlanPicker } from "@/components/plan-picker";
import { loadRunDir, TEXAS_RUN_DIR } from "@/lib/run-dir";
import { TEXAS } from "@/lib/runs";

export default async function TexasPlansPage() {
  return <PlanPicker run={await loadRunDir(TEXAS_RUN_DIR)} base={TEXAS.base} />;
}
