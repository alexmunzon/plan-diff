import { CitationAudit, NoAudit } from "@/components/citation-audit";
import { auditFolder, loadAudit } from "@/lib/audit-dir";
import { TEXAS } from "@/lib/runs";

export default async function TexasAuditPage() {
  const audit = await loadAudit(TEXAS);
  return audit ? <CitationAudit audit={audit} runLabel={TEXAS.label} folder={auditFolder(TEXAS)} /> : <NoAudit runLabel={TEXAS.label} />;
}
