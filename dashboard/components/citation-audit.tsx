"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { SeverityBadge } from "@/components/severity-badge";
import { CARD } from "@/components/tiles";
import {
  CHECK_GROUPS,
  CHECK_TEXT,
  OUTCOME_TEXT,
  VERDICTS,
  VERDICT_TEXT,
  VERDICT_TONE,
  POLICY_TEXT,
  dateWindowText,
  locationText,
  weakenedPolicy,
  type Audit,
  type AuditPartResult,
  type AuditVerdict,
  type ClaimAudit,
  type EvidenceDocument,
} from "@/lib/audit";
import { fieldLabel, fieldValueText } from "@/lib/compare";
import { cn } from "@/lib/utils";

// PR 18: review whether each claim's cited evidence supports it. Every string from a claim or a
// document is rendered as plain text (React escapes it); nothing in them is followed or run.

const MUTED = "text-xs muted";

function Verdict({ verdict }: { verdict: AuditVerdict }) {
  return <SeverityBadge tone={VERDICT_TONE[verdict]} label={VERDICT_TEXT[verdict]} />;
}

export function NoAudit({ runLabel }: { runLabel: string }) {
  return (
    <div className="report-page">
      <header className="page-header">
        <h1 className="page-title">Citation audit</h1>
      </header>
      <section aria-label="No audit" className={cn(CARD, "review-panel")}>
        <h2>No citation audit has been run for {runLabel}.</h2>
        <p className="mt-2 text-sm muted">
          An audit checks claims written about this run against the pages they cite. None exists for this run, so nothing here is checked or approved.
        </p>
      </section>
    </div>
  );
}

function ChecksTable({ checks, caption }: { checks: ClaimAudit["parts"][number]["checks"]; caption: string }) {
  const ordered = CHECK_GROUPS.flatMap(([group, names]) =>
    names.flatMap((name) => checks.filter((c) => c.name === name).map((c) => ({ group, c }))),
  );
  if (ordered.length === 0) return null;
  return (
    <table className="audit-checks w-full text-xs">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr><th scope="col">Question</th><th scope="col">Check</th><th scope="col">Result</th><th scope="col">Why</th></tr>
      </thead>
      <tbody>
        {ordered.map(({ group, c }) => (
          <tr key={`${group}-${c.name}`} aria-label={CHECK_TEXT[c.name] ?? c.name} data-outcome={c.outcome}>
            <td>{group}</td>
            <td>{CHECK_TEXT[c.name] ?? c.name}</td>
            <td className="font-medium">{OUTCOME_TEXT[c.outcome]}</td>
            <td>{c.reason}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PartDetail({ claim, part, documents }: { claim: ClaimAudit["claim"]; part: AuditPartResult; documents: EvidenceDocument[] }) {
  const typed = claim.parts.find((p) => p.part_id === part.part_id);
  return (
    <section aria-label={`Part ${part.part_id}`} className="audit-part space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-sm font-semibold">{typed ? fieldLabel(typed.benefit) : part.part_id}</h4>
        <span className="text-sm">{typed ? fieldValueText(typed.value, typed.unit) : ""}</span>
        <Verdict verdict={part.verdict} />
      </div>
      {typed?.conditions?.length ? <p className={MUTED}>Stated conditions: {typed.conditions.join("; ")}</p> : null}
      <ul aria-label="Reasons" className="list-disc space-y-1 pl-5 text-sm">
        {part.reasons.map((r) => <li key={r}>{r}</li>)}
      </ul>
      <ChecksTable checks={part.checks} caption={`Claim checks for ${part.part_id}`} />
      {part.sources.map((s) => {
        const cited = claim.sources[s.source_index];
        const doc = documents.find((d) => d.document_id === cited.document_id);
        const row = s.checks.find((c) => c.location?.row)?.location?.row;
        return (
          <div key={s.source_index} role="group" aria-label={`Source ${s.source_index + 1}`} className="audit-source space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">Source {s.source_index + 1}:</span>
              <span>{cited.document_id}, page {cited.page}</span>
              <Verdict verdict={s.verdict} />
            </div>
            <dl className="audit-evidence grid gap-x-4 gap-y-1 text-xs sm:grid-cols-[auto_1fr]">
              <dt className="muted">Quote given</dt><dd>{cited.quote ? <q>{cited.quote}</q> : "None"}</dd>
              <dt className="muted">Row read on the page</dt><dd>{row ? <q>{row}</q> : "No row was read"}</dd>
              <dt className="muted">Version</dt>
              <dd>
                {doc
                  ? `${doc.document_type ?? "Unknown type"}, ${doc.plan_id ?? "plan unknown"} ${doc.year ?? "year unknown"}. ${dateWindowText(doc)}.${doc.meta.supersedes.length ? ` Supersedes ${doc.meta.supersedes.join(", ")}.` : ""}`
                  : "Not a document of this run"}
              </dd>
              {doc && <><dt className="muted">Identity</dt><dd className="break-all">SHA-256 {doc.sha256}, {doc.page_index}</dd></>}
            </dl>
            <ChecksTable checks={s.checks} caption={`Checks for source ${s.source_index + 1}`} />
          </div>
        );
      })}
      {part.contrary.length > 0 && (
        <div role="group" aria-label="Contrary evidence" className="space-y-1">
          <h5 className="text-xs font-semibold">Other evidence that reads differently</h5>
          <ul className="space-y-1 text-xs">
            {part.contrary.map((c) => (
              <li key={`${locationText(c.location)}-${c.reason}`}>
                {locationText(c.location)}: {c.reason}
                {c.location.row && c.location.kind === "pdf_page" ? <> (<q>{c.location.row}</q>)</> : null}
                {c.dismissed ? <span className="muted"> Set aside: {c.dismissed}.</span> : null}
              </li>
            ))}
          </ul>
        </div>
      )}
      {part.unknowns.length > 0 && (
        <div role="group" aria-label="Unknowns" className="text-xs">
          <h5 className="font-semibold">Unknown</h5>
          <ul className="list-disc pl-5">{part.unknowns.map((u) => <li key={u}>{u}</li>)}</ul>
        </div>
      )}
    </section>
  );
}

export function CitationAudit({ audit, runLabel, folder }: { audit: Audit; runLabel: string; folder: string }) {
  const { sidecar, manifest } = audit;
  const [filter, setFilter] = useState<AuditVerdict | "all">("all");
  const shown = sidecar.claims.filter((c) => filter === "all" || c.verdict === filter);
  const [selectedId, setSelectedId] = useState(sidecar.claims[0]?.claim.claim_id ?? "");
  const selected = shown.find((c) => c.claim.claim_id === selectedId) ?? shown[0] ?? null;
  const weakened = weakenedPolicy(sidecar);
  return (
    <div className="report-page">
      <header className="page-header">
        <p className="report-eyebrow">
          <span className="run-provenance">{sidecar.data_kind === "synthetic" ? "Synthetic demo" : "Public run"}</span>
          <span>Offline</span>
          <span>Model lane: not run</span>
        </p>
        <h1 className="page-title">Does the cited evidence support each claim?</h1>
        <p className="page-context">{sidecar.notice}</p>
        <dl aria-label="About this audit" className="trust-context grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          <dt className={MUTED}>Run</dt><dd>{runLabel}, run {sidecar.run_id}</dd>
          <dt className={MUTED}>Audit</dt><dd>{sidecar.audit_id}, {manifest.claims} claims, {manifest.pdf_reads} PDFs read once each ({manifest.pages_read} pages)</dd>
          <dt className={MUTED}>Checked by</dt><dd>Deterministic rules, plan-diff {manifest.engine_version}, commit {manifest.git_commit.slice(0, 12)}{manifest.git_dirty ? " with uncommitted changes" : ""}</dd>
          <dt className={MUTED}>Not done</dt><dd>No model was called. No person has adjudicated these claims.</dd>
        </dl>
        {weakened.length > 0 && (
          <p role="alert" className="audit-weakened mt-3 text-sm font-medium">
            Safeguards were switched off for this audit: {weakened.map((k) => POLICY_TEXT[k]).join("; ")}. This is a test of the checks, not a real audit, and its verdicts must not be relied on.
          </p>
        )}
      </header>

      <section aria-labelledby="audit-filter-heading" className={cn(CARD, "review-panel")}>
        <h2 id="audit-filter-heading">Filter by verdict</h2>
        <div role="group" aria-label="Verdict filter" className="audit-filter mt-3 flex flex-wrap gap-2">
          <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")} className="audit-chip">
            All ({sidecar.claims.length})
          </button>
          {VERDICTS.map((v) => (
            <button key={v} type="button" aria-pressed={filter === v} onClick={() => setFilter(v)} className="audit-chip" disabled={!sidecar.counts[v]}>
              {VERDICT_TEXT[v]} ({sidecar.counts[v] ?? 0})
            </button>
          ))}
        </div>
      </section>

      <div className="audit-layout">
        <section aria-labelledby="audit-claims-heading" className={cn(CARD, "review-panel")}>
          <h2 id="audit-claims-heading">Claims</h2>
          {shown.length === 0 ? (
            <p className="mt-2 text-sm muted">No claims have this verdict.</p>
          ) : (
            <ul aria-label="Claims" className="audit-claims mt-3 space-y-2">
              {shown.map((c) => (
                <li key={c.claim.claim_id}>
                  <button
                    type="button"
                    className="audit-claim"
                    aria-current={selected?.claim.claim_id === c.claim.claim_id ? "true" : undefined}
                    aria-controls="audit-detail"
                    onClick={() => setSelectedId(c.claim.claim_id)}
                  >
                    <span className="block text-sm">{c.claim.text}</span>
                    <span className="mt-1 flex flex-wrap items-center gap-2">
                      <Verdict verdict={c.verdict} />
                      <span className={MUTED}>{c.claim.plan_id} {c.claim.year}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {selected && (
          <section id="audit-detail" aria-labelledby="audit-detail-heading" aria-live="polite" className={cn(CARD, "review-panel space-y-4")}>
            <div>
              <h2 id="audit-detail-heading">{selected.claim.claim_id}</h2>
              <p className="mt-2 text-sm">{selected.claim.text}</p>
              <p className={cn(MUTED, "mt-1")}>
                {selected.claim.plan_id}, plan year {selected.claim.year}
                {selected.claim.as_of ? `, as of ${selected.claim.as_of}` : ", no as-of date stated"}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2"><span className="text-sm font-medium">Verdict:</span><Verdict verdict={selected.verdict} /></div>
            </div>
            <div>
              <h3 className="text-sm font-semibold">Why</h3>
              <ul aria-label="Claim reasons" className="mt-1 list-disc space-y-1 pl-5 text-sm">
                {selected.reasons.map((r) => <li key={r}>{r}</li>)}
              </ul>
            </div>
            {selected.parts.map((p) => <PartDetail key={p.part_id} claim={selected.claim} part={p} documents={sidecar.documents} />)}
            <dl aria-label="Provenance" className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-[auto_1fr]">
              <dt className="muted">Decided by</dt><dd>{selected.origin.replaceAll("_", " ")}; model lane not run</dd>
              <dt className="muted">Uncertainty</dt><dd>{selected.uncertainty}</dd>
            </dl>
          </section>
        )}
      </div>

      <section aria-label="Download the audit" className={cn(CARD, "review-panel")}>
        <h2>Download the audit</h2>
        <ul className="mt-2 flex flex-wrap gap-4 text-sm">
          <li><a className="flex items-center gap-2 underline" href={`/${folder}/audit.json`} download><Download aria-hidden className="size-3" />Audit JSON</a></li>
          <li><a className="flex items-center gap-2 underline" href={`/${folder}/audit_manifest.json`} download><Download aria-hidden className="size-3" />Audit manifest JSON</a></li>
        </ul>
      </section>
    </div>
  );
}
