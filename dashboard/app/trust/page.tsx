import { Trust } from "@/components/trust";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";

export default async function TrustPage() {
  return <Trust run={await loadRunDir(DEMO_RUN_DIR)} />;
}
