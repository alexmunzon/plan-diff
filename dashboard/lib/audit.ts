import { check, moneyIsText, object, parseJson } from "@/lib/run-loader";
import type { FieldValue } from "@/lib/types";

// PR 18: the citation audit sidecar, mirroring engine/src/plan_diff/audit/models.py. Shape checks
// only (the engine's models are the validator), plus the checks that keep the page honest: the
// audit finished, it was made for this exact run, and its counts recompute from its claims.

export const VERDICTS = [
  "supported",
  "contradicted",
  "conflicting_evidence",
  "inapplicable_version",
  "insufficient_evidence",
  "unverifiable",
  "needs_human_review",
] as const;
export type AuditVerdict = (typeof VERDICTS)[number];

export interface AuditLocation {
  kind: "pdf_page" | "cms_row";
  document_id: string;
  page: number;
  printed_page: string | null;
  row: string | null;
}

export interface AuditCheck {
  name: string;
  lane: "deterministic" | "model";
  outcome: "pass" | "fail" | "unknown" | "not_run";
  reason: string;
  location: AuditLocation | null;
}

export interface AuditSourceResult { source_index: number; verdict: AuditVerdict; checks: AuditCheck[] }
export interface AuditContrary { location: AuditLocation; reason: string; dismissed: string | null }

export interface AuditPartResult {
  part_id: string;
  checks: AuditCheck[];
  verdict: AuditVerdict;
  reasons: string[];
  sources: AuditSourceResult[];
  contrary: AuditContrary[];
  unknowns: string[];
}

export interface ClaimSource { document_id: string; page: number; quote?: string | null; sha256?: string | null; parts?: string[] }

export interface ClaimPart {
  part_id: string;
  benefit: string;
  value: FieldValue | null;
  unit: string | null;
  network?: "in_network" | "out_of_network" | null;
  conditions?: string[];
}

export interface Claim {
  claim_id: string;
  text: string;
  plan_id: string;
  year: number;
  as_of?: string | null;
  parts: ClaimPart[];
  sources: ClaimSource[];
}

export interface ClaimAudit {
  claim: Claim;
  verdict: AuditVerdict;
  reasons: string[];
  parts: AuditPartResult[];
  origin: string;
  model_lane: "not_run";
  uncertainty: string;
}

export interface EvidenceDocument {
  document_id: string;
  sha256: string;
  size_bytes: number;
  page_count: number;
  page_index: string;
  plan_id: string | null;
  year: number | null;
  document_type: string | null;
  readable: boolean;
  problem: string | null;
  meta: {
    effective_from: string | null;
    effective_to: string | null;
    supersedes: string[];
    printed_page_labels: Record<string, string>;
    note: string | null;
  };
}

export interface AuditSidecar {
  schema_version: "citation-audit-v1";
  audit_id: string;
  data_kind: "synthetic" | "public";
  run_id: string | null;
  policy: Record<string, boolean>;
  documents: EvidenceDocument[];
  claims: ClaimAudit[];
  counts: Record<string, number>;
  notice: string;
}

export interface AuditManifest {
  schema_version: "citation-audit-manifest-v2";
  audit_id: string;
  status: "complete";
  started_at: string;
  finished_at: string;
  command: string[];
  engine_version: string;
  git_commit: string;
  git_dirty: boolean | null;
  hashes: Record<string, string>;
  pdf_reads: number;
  pages_read: number;
  claims: number;
  verdicts: Record<string, number>;
  model_lane: "not_run";
  libraries?: Record<string, string>;
}

export interface Audit { sidecar: AuditSidecar; manifest: AuditManifest }

export const AUDIT_FILES = { audit: "audit.json", manifest: "audit_manifest.json" };

// The engine's Policy switches. All on is the real audit; any switched off is a negative control.
export const POLICY_KEYS = ["require_support", "check_plan_year", "check_effective_dates", "check_contrary", "unknown_blocks", "unknown_dates_block"] as const;

export const POLICY_TEXT: Record<(typeof POLICY_KEYS)[number], string> = {
  require_support: "support checks (citation existence alone was accepted)",
  check_plan_year: "plan and year checks",
  check_effective_dates: "effective date and supersession checks",
  check_contrary: "the search for contrary evidence",
  unknown_blocks: "unknowns blocking support",
  unknown_dates_block: "unknown effective dates blocking support (the policy before 2026-10-25)",
};

/** The safeguards an audit ran with switched off. Empty for a real audit. */
export const weakenedPolicy = (sidecar: AuditSidecar) => POLICY_KEYS.filter((k) => !sidecar.policy[k]);

export interface RunBinding { runId: string; dataKind: string; manifestSha256: string; validationSha256: string }

/** Validate structure and the completion contract. The server supplies a digest of the raw
 * audit bytes, before UTF-8 decoding. This binds files, not the authenticity of their author. */
export function parseAudit(files: { audit: string; manifest: string }, run: RunBinding, auditSha256: string): Audit {
  const where = AUDIT_FILES.audit;
  const sidecar = object(parseJson(files.audit, where), where, ["schema_version", "audit_id", "data_kind", "run_id", "policy", "documents", "claims", "counts", "notice"]);
  check(sidecar.schema_version === "citation-audit-v1", where, "unknown schema_version");
  const manifest = object(parseJson(files.manifest, AUDIT_FILES.manifest), AUDIT_FILES.manifest, ["audit_id", "status", "command", "engine_version", "git_commit", "git_dirty", "hashes", "pdf_reads", "pages_read", "claims", "verdicts", "model_lane"]);
  check(manifest.schema_version === "citation-audit-manifest-v2", AUDIT_FILES.manifest, "a completed v2 manifest is required; regenerate legacy output from its inputs");
  check(typeof manifest.git_commit === "string" && typeof manifest.engine_version === "string", AUDIT_FILES.manifest, "commit and engine version must be text");
  check(manifest.status === "complete", AUDIT_FILES.manifest, "the audit did not finish");
  check(manifest.model_lane === "not_run", AUDIT_FILES.manifest, "only audits with the model lane not run are shown");
  check(manifest.audit_id === sidecar.audit_id, AUDIT_FILES.manifest, "audit_id differs from audit.json");
  const hashes = object(manifest.hashes, AUDIT_FILES.manifest, ["audit"]) as Record<string, string>;
  check(typeof hashes.audit === "string" && /^[0-9a-f]{64}$/.test(hashes.audit) && hashes.audit === auditSha256, where, "audit bytes differ from the completion manifest");
  check(hashes.run_manifest === run.manifestSha256, where, "this audit was made for a different run");
  check(hashes.run_validation === run.validationSha256, where, "this audit was made from different CMS validation results");
  const policy = object(sidecar.policy, `${where} policy`, [...POLICY_KEYS]);
  check(Object.keys(policy).length === POLICY_KEYS.length && Object.values(policy).every((v) => typeof v === "boolean"), `${where} policy`, "unknown policy switches");
  check(sidecar.run_id === run.runId && sidecar.data_kind === run.dataKind, where, "run id or data kind differs from the run");
  check(Array.isArray(sidecar.claims) && Array.isArray(sidecar.documents), where, "claims and documents must be lists");
  (sidecar.documents as unknown[]).forEach((d, i) => {
    const doc = object(d, `${where} document ${i + 1}`, ["document_id", "sha256", "page_index", "plan_id", "year", "document_type", "readable", "meta"]);
    object(doc.meta, `${where} document ${i + 1} meta`, ["effective_from", "effective_to", "supersedes", "printed_page_labels"]);
  });
  const claims = sidecar.claims as ClaimAudit[];
  const documents = sidecar.documents as EvidenceDocument[];
  check(new Set(documents.map((d) => d.document_id)).size === documents.length, where, "duplicate document identity");
  claims.forEach((c, i) => checkClaim(c, `${where} claim ${i + 1}`, documents, policy as Record<string, boolean>));
  moneyIsText(sidecar.claims, where);
  const counts = sidecar.counts as Record<string, number>;
  check(counts.claims === claims.length && manifest.claims === claims.length, where, "the claim count differs from the claims listed");
  for (const v of VERDICTS) {
    const n = claims.filter((c) => c.verdict === v).length;
    check(counts[v] === n && (manifest.verdicts as Record<string, number>)[v] === n, where, `the ${v} count does not recompute`);
  }
  return { sidecar: sidecar as unknown as AuditSidecar, manifest: manifest as unknown as AuditManifest };
}

const isVerdict = (v: unknown) => (VERDICTS as readonly unknown[]).includes(v);

// The engine's claim-level precedence (checks.py CLAIM_ORDER): the first verdict any part has.
const CLAIM_ORDER: AuditVerdict[] = ["contradicted", "conflicting_evidence", "inapplicable_version", "unverifiable", "insufficient_evidence", "needs_human_review", "supported"];

/** A claim's result must cover exactly its declared parts, in order, and its verdict must follow
 * from theirs, so a result with parts removed can never show as a bare "Supported". */
function checkClaim(c: ClaimAudit, where: string, documents: EvidenceDocument[], policy: Record<string, boolean>): void {
  object(c, where, ["claim", "verdict", "reasons", "parts", "uncertainty"]);
  object(c.claim, where, ["parts", "sources"]);
  check(isVerdict(c.verdict), where, "unknown verdict");
  check(c.origin === "deterministic_rules_v1" && c.model_lane === "not_run", where, "only deterministic results with the model lane not run are shown");
  check(Array.isArray(c.parts) && Array.isArray(c.claim.parts) && Array.isArray(c.claim.sources), where, "parts and sources must be lists");
  const declared = c.claim.parts.map((p) => p.part_id).join("\n");
  check(c.claim.parts.length > 0 && new Set(c.claim.parts.map((p) => p.part_id)).size === c.claim.parts.length, where, "declared parts must be nonempty and unique");
  check(c.parts.map((p) => p.part_id).join("\n") === declared, where, "its results do not cover exactly the claim's parts");
  for (const p of c.parts) {
    object(p, `${where} part ${p.part_id}`, ["checks", "verdict", "reasons", "sources", "contrary", "unknowns"]);
    check(isVerdict(p.verdict), `${where} part ${p.part_id}`, "unknown verdict");
    check(Array.isArray(p.checks) && p.checks.every(validCheck), `${where} part ${p.part_id}`, "wording checks are malformed");
    check(Array.isArray(p.sources) && Array.isArray(p.contrary), `${where} part ${p.part_id}`, "sources and contrary evidence must be lists");
    for (const s of p.sources) {
      check(isVerdict(s.verdict) && Number.isInteger(s.source_index) && s.source_index >= 0 && s.source_index < c.claim.sources.length, `${where} part ${p.part_id}`, "a source result names no cited source");
      check(Array.isArray(s.checks) && s.checks.every(validCheck), `${where} part ${p.part_id}`, "a source's checks are malformed");
      if (s.verdict === "supported") {
        const source = c.claim.sources[s.source_index];
        const doc = documents.find((d) => d.document_id === source.document_id);
        check(doc?.readable === true && Number.isInteger(source.page) && source.page > 0 && source.page <= doc.page_count && (!source.sha256 || source.sha256 === doc.sha256), `${where} part ${p.part_id}`, "a supported source has no consistent document evidence");
        const required = ["source_resolves", "hash_matches", "page_in_range"];
        // The unknowns-off mutant can stop at an ambiguous row before later checks run.
        // It remains visibly marked as weakened; the normal policy requires the full chain.
        if (policy.require_support && policy.unknown_blocks) {
          required.push("row_found", "row_in_grammar", "network_matches", "page_has_no_qualifiers", "value_matches");
          if (policy.check_plan_year) required.push("plan_year_matches");
          if (policy.check_effective_dates) required.push("effective_date_applies", "not_superseded");
          if (source.quote) required.push("quote_on_page", "quote_covers_row");
          if (c.claim.parts.find((part) => part.part_id === p.part_id)?.conditions?.length) required.push("conditions_present");
        }
        check(showsSupport(s.checks, required, policy), `${where} part ${p.part_id}`, "a supported source does not show its evidence");
      }
    }
    check(p.verdict !== "supported" || p.sources.some((s) => s.verdict === "supported"), `${where} part ${p.part_id}`, "a supported part has no supporting source");
    if (p.verdict === "supported" && policy.require_support) {
      check(showsSupport(p.checks, ["text_matches_parts"], policy), `${where} part ${p.part_id}`, "a supported part has inconsistent wording checks");
      check(!policy.check_contrary || !policy.unknown_blocks || p.contrary.every((e) => e.dismissed !== null), `${where} part ${p.part_id}`, "a supported part has live contrary evidence");
    }
  }
  check(c.verdict === CLAIM_ORDER.find((v) => c.parts.some((p) => p.verdict === v)), where, "its verdict does not follow from its parts");
}

function validCheck(k: AuditCheck): boolean {
  return k !== null && typeof k === "object" && typeof k.name === "string" && typeof k.reason === "string" && k.lane === "deterministic" && ["pass", "fail", "unknown", "not_run"].includes(k.outcome);
}

function showsSupport(checks: AuditCheck[], required: string[], policy: Record<string, boolean>): boolean {
  const acceptable = (k: AuditCheck) => k.outcome === "pass" || (k.outcome === "unknown" && (!policy.unknown_blocks || (k.name === "effective_date_applies" && !policy.unknown_dates_block)));
  return new Set(checks.map((k) => k.name)).size === checks.length
    && !checks.some((k) => k.outcome === "fail" || (k.outcome === "unknown" && !acceptable(k)))
    && required.every((name) => checks.some((k) => k.name === name && acceptable(k)));
}

export const VERDICT_TEXT: Record<AuditVerdict, string> = {
  supported: "Supported",
  contradicted: "Contradicted",
  conflicting_evidence: "Conflicting evidence",
  inapplicable_version: "Wrong plan, year, or version",
  insufficient_evidence: "Insufficient evidence",
  unverifiable: "Source cannot be checked",
  needs_human_review: "Needs a person",
};

export const VERDICT_TONE: Record<AuditVerdict, "pass" | "error" | "warning" | "info"> = {
  supported: "pass",
  contradicted: "error",
  conflicting_evidence: "warning",
  inapplicable_version: "warning",
  insufficient_evidence: "warning",
  unverifiable: "error",
  needs_human_review: "info",
};

// The checks in the order a reviewer reads them, grouped by the question each answers.
export const CHECK_GROUPS: [title: string, names: string[]][] = [
  ["Claim wording", ["text_matches_parts"]],
  ["Citation", ["source_resolves", "hash_matches", "page_in_range", "quote_on_page"]],
  ["Version and context", ["plan_year_matches", "plan_pages", "effective_date_applies", "not_superseded"]],
  ["Support", ["row_found", "quote_covers_row", "row_in_grammar", "network_matches", "page_has_no_qualifiers", "conditions_present", "value_matches"]],
];

export const CHECK_TEXT: Record<string, string> = {
  text_matches_parts: "Claim words match its typed parts",
  source_resolves: "Document is part of the run",
  hash_matches: "File bytes match the run's hash",
  page_in_range: "Cited page exists",
  quote_on_page: "Quote is on the cited page",
  plan_year_matches: "Document is for this plan and year",
  plan_pages: "Page belongs to this plan in the booklet",
  effective_date_applies: "Effective on the claim date",
  not_superseded: "Not replaced by a newer document",
  row_found: "One benefit row on the page",
  quote_covers_row: "Quote is the row that was checked",
  row_in_grammar: "Row holds one plain value",
  network_matches: "Network matches",
  page_has_no_qualifiers: "No qualifying wording on the page",
  conditions_present: "Stated conditions are in the row",
  value_matches: "Row states the claimed value",
};

export const OUTCOME_TEXT: Record<AuditCheck["outcome"], string> = { pass: "Pass", fail: "Fail", unknown: "Unknown", not_run: "Not run" };

export function locationText(location: AuditLocation): string {
  if (location.kind === "cms_row") return `CMS file ${location.document_id}, row ${location.page}`;
  const printed = location.printed_page ? ` (printed page ${location.printed_page})` : "";
  return `${location.document_id}, page ${location.page}${printed}`;
}

export function dateWindowText(doc: EvidenceDocument): string {
  const { effective_from: from, effective_to: to } = doc.meta;
  if (!from && !to) return "Effective dates unknown (not declared)";
  return `Effective ${from ?? "unknown"} to ${to ?? "unknown"}`;
}
