import { Overview } from "@/components/overview";
import { loadRunDir, TEXAS_RUN_DIR } from "@/lib/run-dir";
import { TEXAS } from "@/lib/runs";

// PR 15: the real Texas run (public carrier documents checked against real CMS files), read at
// build time from public/texas-run. The carrier PDFs are linked at their own https URLs only.
export default async function TexasOverviewPage() {
  return <Overview run={await loadRunDir(TEXAS_RUN_DIR)} base={TEXAS.base} />;
}
