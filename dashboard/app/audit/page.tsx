import { CitationAudit, NoAudit } from "@/components/citation-audit";
import { auditFolder, loadAudit } from "@/lib/audit-dir";
import { DEMO } from "@/lib/runs";

export default async function AuditPage() {
  const audit = await loadAudit(DEMO);
  return audit ? <CitationAudit audit={audit} runLabel={DEMO.label} folder={auditFolder(DEMO)} /> : <NoAudit runLabel={DEMO.label} />;
}
