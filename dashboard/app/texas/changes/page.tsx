import { Changes } from "@/components/changes";
import { loadRunDir, TEXAS_RUN_DIR } from "@/lib/run-dir";
import { TEXAS } from "@/lib/runs";

export default async function TexasChangesPage() {
  return <Changes run={await loadRunDir(TEXAS_RUN_DIR)} base={TEXAS.base} />;
}
