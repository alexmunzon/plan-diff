import { Overview } from "@/components/overview";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";

// The committed demo run is read at build time from public/demo-run. The dashboard makes no
// network calls and never serves a carrier PDF.
export default async function OverviewPage() {
  return <Overview run={await loadRunDir(DEMO_RUN_DIR)} />;
}
