import { Documents } from "@/components/documents";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";

export default async function DocumentsPage() {
  return <Documents run={await loadRunDir(DEMO_RUN_DIR)} />;
}
