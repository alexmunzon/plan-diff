import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";

import { parseAudit as parseBoundAudit, VERDICTS, weakenedPolicy, type RunBinding } from "@/lib/audit";
import { auditDir, checkPolicy, loadAudit } from "@/lib/audit-dir";
import { DEMO_RUN_DIR } from "@/lib/run-dir";
import { DEMO, TEXAS } from "@/lib/runs";

async function files() {
  const dir = auditDir(DEMO);
  return { audit: await readFile(path.join(dir, "audit.json"), "utf8"), manifest: await readFile(path.join(dir, "audit_manifest.json"), "utf8") };
}

async function binding() {
  const sha = async (name: string) => createHash("sha256").update(await readFile(path.join(DEMO_RUN_DIR, name))).digest("hex");
  return { runId: "demo", dataKind: "synthetic", manifestSha256: await sha("manifest.json"), validationSha256: await sha("validation.json") };
}

// The next access() call fails with this error, once; every other call is the real one.
const accessFails = vi.hoisted(() => ({ next: null as Error | null }));
vi.mock("node:fs/promises", async (importOriginal) => {
  const real = await importOriginal<typeof import("node:fs/promises")>();
  const access: typeof real.access = async (...args) => {
    const error = accessFails.next;
    accessFails.next = null;
    if (error) throw error;
    return real.access(...args);
  };
  return { ...real, default: { ...real, access }, access };
});

type Files = { audit: string; manifest: string };
const sha = (text: string) => createHash("sha256").update(text).digest("hex");

// These synthetic structural/negative-policy controls intentionally rebind their changed
// bytes so each existing semantic gate is still exercised. Corruption tests below retain
// the original manifest and call the real parser directly.
function parseAudit(files: Files, run: RunBinding) {
  const manifest = JSON.parse(files.manifest);
  manifest.hashes.audit = sha(files.audit);
  return parseBoundAudit({ ...files, manifest: JSON.stringify(manifest) }, run, sha(files.audit));
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const edit = (f: Files, change: (audit: any) => void) => {
  const audit = JSON.parse(f.audit);
  change(audit);
  return { ...f, audit: JSON.stringify(audit) };
};

describe("citation audit loader", () => {
  it.each(["text", "amount", "whitespace"])("refuses changed %s bytes with the retained manifest", async (fault) => {
    const good = await files();
    const changed = fault === "whitespace" ? { ...good, audit: good.audit + "\n" }
      : edit(good, (a) => {
        if (fault === "text") a.claims[0].claim.text = "The premium is $999.";
        else a.claims[0].claim.parts[0].value.amount = "999.00";
      });
    const run = await binding();
    expect(() => parseBoundAudit(good, run, sha(good.audit))).not.toThrow();
    expect(() => parseBoundAudit(changed, run, sha(changed.audit))).toThrow(/audit bytes differ/);
  });

  it.each(["missing_version", "legacy", "unknown_version", "missing_digest", "invalid_digest"])("refuses %s completion metadata", async (fault) => {
    const good = await files();
    const manifest = JSON.parse(good.manifest);
    if (fault === "missing_version") delete manifest.schema_version;
    if (fault === "legacy") manifest.schema_version = "citation-audit-manifest-v1";
    if (fault === "unknown_version") manifest.schema_version = "unknown";
    if (fault === "missing_digest") delete manifest.hashes.audit;
    if (fault === "invalid_digest") manifest.hashes.audit = "invalid";
    const run = await binding();
    expect(() => parseBoundAudit({ ...good, manifest: JSON.stringify(manifest) }, run, sha(good.audit))).toThrow(/v2 manifest|missing audit|audit bytes differ/);
  });
  it("loads the demo audit, bound to the committed demo run", async () => {
    const audit = await loadAudit(DEMO);
    expect(audit?.sidecar.claims).toHaveLength(8);
    expect(audit?.manifest.model_lane).toBe("not_run");
    const total = VERDICTS.reduce((n, v) => n + (audit?.sidecar.counts[v] ?? 0), 0);
    expect(total).toBe(8);
  });

  it("shows no audit for a run that has none, rather than borrowing the demo's", async () => {
    expect(await loadAudit(TEXAS)).toBeNull();
  });

  it.each([
    ["a different run", (f: { audit: string; manifest: string }) => ({ ...f, manifest: f.manifest.replace(/"run_manifest": "[0-9a-f]+"/, `"run_manifest": "${"0".repeat(64)}"`) }), /different run/],
    ["an unfinished audit", (f: { audit: string; manifest: string }) => ({ ...f, manifest: f.manifest.replace('"status": "complete"', '"status": "started"') }), /did not finish/],
    ["a forged count", (f: { audit: string; manifest: string }) => ({ ...f, audit: f.audit.replace('"supported": 1', '"supported": 3') }), /does not recompute/],
    ["money as a number", (f: { audit: string; manifest: string }) => ({ ...f, audit: f.audit.replace('"amount": "25.00"', '"amount": 25') }), /amount must be text/],
    ["other CMS validation results", (f: { audit: string; manifest: string }) => ({ ...f, manifest: f.manifest.replace(/"run_validation": "[0-9a-f]+"/, `"run_validation": "${"0".repeat(64)}"`) }), /different CMS validation/],
    ["a supported claim with its parts removed", (f: Files) => edit(f, (a) => { a.claims[0].parts = []; }), /exactly the claim's parts/],
    ["a verdict its parts do not give", (f: Files) => edit(f, (a) => { a.claims[0].parts[0].verdict = "contradicted"; }), /does not follow from its parts/],
    ["a source result for no cited source", (f: Files) => edit(f, (a) => { a.claims[0].parts[0].sources[0].source_index = 9; }), /names no cited source/],
    ["a missing policy", (f: Files) => edit(f, (a) => { delete a.policy; }), /missing policy/],
    ["an unknown policy switch", (f: Files) => edit(f, (a) => { a.policy.trust_me = true; }), /unknown policy switches/],
    ["a supported part with its evidence removed", (f: Files) => edit(f, (a) => { a.claims[0].parts[0].sources = []; a.claims[0].parts[0].checks = []; }), /no supporting source/],
    ["a supported source without a matching value", (f: Files) => edit(f, (a) => { a.claims[0].parts[0].sources[0].checks = a.claims[0].parts[0].sources[0].checks.filter((k: { name: string }) => k.name !== "value_matches"); }), /does not show its evidence/],
    ["a supported source with a failed check", (f: Files) => edit(f, (a) => { a.claims[0].parts[0].sources[0].checks[0].outcome = "fail"; }), /does not show its evidence/],
    ["supported text with a failed wording check", (f: Files) => edit(f, (a) => { a.claims[0].parts[0].checks[0].outcome = "fail"; }), /wording checks/],
    ["supported text with an unknown wording check", (f: Files) => edit(f, (a) => { a.claims[0].parts[0].checks[0].outcome = "unknown"; }), /wording checks/],
    ["supported text with no wording check", (f: Files) => edit(f, (a) => { a.claims[0].parts[0].checks = []; }), /wording checks/],
    ["a supported source with unknown dates", (f: Files) => edit(f, (a) => { a.claims[0].parts[0].sources[0].checks.find((k: { name: string }) => k.name === "effective_date_applies").outcome = "unknown"; }), /does not show its evidence/],
    ["a supported source with its document removed", (f: Files) => edit(f, (a) => { a.documents = a.documents.filter((d: { document_id: string }) => d.document_id !== a.claims[0].claim.sources[0].document_id); }), /document evidence/],
    ["a supported source with an unreadable document", (f: Files) => edit(f, (a) => { a.documents.find((d: { document_id: string }) => d.document_id === a.claims[0].claim.sources[0].document_id).readable = false; }), /document evidence/],
    ["a supported source with a missing context check", (f: Files) => edit(f, (a) => { a.claims[0].parts[0].sources[0].checks = a.claims[0].parts[0].sources[0].checks.filter((k: { name: string }) => k.name !== "plan_year_matches"); }), /does not show its evidence/],
    ["a supported part with live contrary evidence", (f: Files) => edit(f, (a) => { a.claims[0].parts[0].contrary = [{ location: { kind: "cms_row", document_id: "synthetic.csv", page: 1 }, reason: "recorded disagreement", dismissed: null }]; }), /contrary evidence/],
    ["a claim decided by a model", (f: Files) => edit(f, (a) => { a.claims[0].model_lane = "run"; }), /model lane not run/],
    ["a document without metadata", (f: Files) => edit(f, (a) => { delete a.documents[0].meta; }), /missing meta/],
    ["a manifest claim total that does not recompute", (f: Files) => ({ ...f, manifest: f.manifest.replace('"claims": 8', '"claims": 999') }), /claim count differs/],
    ["a manifest without its commit", (f: Files) => ({ ...f, manifest: f.manifest.replace(/"git_commit": "[^"]*",/, "") }), /missing git_commit/],
  ])("refuses %s", async (_, change, message) => {
    const run = await binding();
    const good = await files();
    expect(() => parseAudit(good, run)).not.toThrow();
    expect(() => parseAudit(change(good), run)).toThrow(message);
  });

  it("discloses an audit run with safeguards switched off", async () => {
    const good = await files();
    const audit = parseAudit(edit(good, (a) => { a.policy.check_contrary = false; }), await binding());
    expect(weakenedPolicy(audit.sidecar)).toEqual(["check_contrary"]);
    expect(weakenedPolicy(parseAudit(good, await binding()).sidecar)).toEqual([]);
  });

  it("refuses a policy that differs from the one the manifest fingerprinted", async () => {
    const audit = await loadAudit(DEMO);
    if (!audit) throw new Error("demo audit missing");
    expect(() => checkPolicy(audit)).not.toThrow();
    audit.sidecar.policy.check_contrary = false;
    expect(() => checkPolicy(audit)).toThrow(/policy differs/);
  });

  it.each(["unclear contrary evidence", "ambiguous row"])("keeps the unknowns-off control inspectable with %s", async (scenario) => {
    const changed = edit(await files(), (a) => {
      const part = a.claims[0].parts[0];
      if (scenario === "unclear contrary evidence") {
        part.contrary = [{ location: { kind: "pdf_page", document_id: "a", page: 1 }, reason: "unclear applicability", dismissed: null }];
      } else {
        part.sources[0].checks = part.sources[0].checks.filter((k: { name: string }) => ["source_resolves", "hash_matches", "page_in_range", "row_found"].includes(k.name));
        part.sources[0].checks.find((k: { name: string }) => k.name === "row_found").outcome = "unknown";
      }
    });
    const run = await binding();
    expect(() => parseAudit(changed, run)).toThrow();
    const control = parseAudit(edit(changed, (a) => { a.policy.unknown_blocks = false; }), run);
    expect(weakenedPolicy(control.sidecar)).toEqual(["unknown_blocks"]);
  });

  it("treats only a missing folder as no audit; other read errors are shown", async () => {
    accessFails.next = Object.assign(new Error("EACCES: permission denied"), { code: "EACCES" });
    await expect(loadAudit(DEMO)).rejects.toThrow(/Could not read the audit folder/);
    accessFails.next = Object.assign(new Error("ENOENT: no such file"), { code: "ENOENT" });
    expect(await loadAudit(DEMO)).toBeNull();
  });
});
