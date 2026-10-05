import { Changes } from "@/components/changes";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";

export default async function ChangesPage() {
  return <Changes run={await loadRunDir(DEMO_RUN_DIR)} />;
}
