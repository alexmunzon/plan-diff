import { Trust } from "@/components/trust";
import { loadRunDir, TEXAS_RUN_DIR } from "@/lib/run-dir";

export default async function TexasTrustPage() {
  return <Trust run={await loadRunDir(TEXAS_RUN_DIR)} />;
}
