import { createHash } from "node:crypto";
import { access, readFile } from "node:fs/promises";
import path from "node:path";

import { AUDIT_FILES, parseAudit, type Audit } from "@/lib/audit";
import { FILE_NAMES } from "@/lib/run-loader";
import type { RunChoice } from "@/lib/runs";

// Server only. An audit lives next to its run, never inside it: public/<run folder>-audit.
export const auditDir = (run: RunChoice) => path.join(process.cwd(), "public", `${run.folder}-audit`);
export const auditFolder = (run: RunChoice) => `${run.folder}-audit`;

/** The run's audit, or null when this run has none. An unfinished, unreadable, or mismatched
 * audit throws: only a folder that does not exist means "no audit". */
export async function loadAudit(run: RunChoice): Promise<Audit | null> {
  const dir = auditDir(run);
  try {
    await access(dir);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw new Error(`Could not read the audit folder ${dir}: ${(error as Error).message}`);
  }
  const read = async (name: string) => {
    try {
      return await readFile(path.join(dir, name), "utf8");
    } catch {
      throw new Error(`Incomplete audit: could not read ${name} in ${dir}`);
    }
  };
  const runDir = path.join(process.cwd(), "public", run.folder);
  const runManifest = await readFile(path.join(runDir, FILE_NAMES.manifest));
  const validation = await readFile(path.join(runDir, FILE_NAMES.validation));
  const parsed = JSON.parse(runManifest.toString("utf8")) as { run_id: string; data_kind: string };
  const sha = (bytes: Buffer | string) => createHash("sha256").update(bytes).digest("hex");
  const audit = parseAudit(
    { audit: await read(AUDIT_FILES.audit), manifest: await read(AUDIT_FILES.manifest) },
    { runId: parsed.run_id, dataKind: parsed.data_kind, manifestSha256: sha(runManifest), validationSha256: sha(validation) },
  );
  checkPolicy(audit);
  return audit;
}

/** The policy as the engine hashes it: Python's json.dumps(policy, sort_keys=True). */
export function policyText(policy: Record<string, boolean>): string {
  return `{${Object.keys(policy).sort().map((k) => `${JSON.stringify(k)}: ${policy[k]}`).join(", ")}}`;
}

/** The policy shown (and any warning about it) must be the one the manifest fingerprinted. */
export function checkPolicy(audit: Audit): void {
  const hash = createHash("sha256").update(policyText(audit.sidecar.policy)).digest("hex");
  if (hash !== audit.manifest.hashes.policy) throw new Error(`${AUDIT_FILES.audit}: its policy differs from the one the manifest recorded`);
}
