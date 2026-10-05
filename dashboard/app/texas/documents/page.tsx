import { Documents } from "@/components/documents";
import { loadRunDir, TEXAS_RUN_DIR } from "@/lib/run-dir";

export default async function TexasDocumentsPage() {
  return <Documents run={await loadRunDir(TEXAS_RUN_DIR)} />;
}
