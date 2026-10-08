import { CitationText, TABLE, TD, TH } from "@/components/change-parts";
import { SeverityBadge } from "@/components/severity-badge";
import { RunEyebrow } from "@/components/run-eyebrow";
import { CARD } from "@/components/tiles";
import { fieldLabel, fieldValueText, reviewKindText } from "@/lib/compare";
import type { Run } from "@/lib/run-loader";
import { REVIEW_EXPLANATIONS, accuracyLabel, asOf, dataKindText, matchRateText, methodText, reviewGroups, sliceText } from "@/lib/trust";
import { cn } from "@/lib/utils";

const SEVERITY_TONE = { high: "error", medium: "warning", low: "info" } as const;
const sentence = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);
const MUTED = "text-xs muted";
const COUNTS = [
  ["matched", "Matched"],
  ["mismatched", "Mismatched"],
  ["not_comparable", "Not comparable"],
  ["not_extracted", "Not extracted"],
  ["not_in_cms", "Not in CMS"],
] as const;

function accuracyScope(run: Run) {
  const totalRows = run.accuracy.rows.filter((row) => row.field === null);
  const count = (key: "matched" | "mismatched" | "not_comparable" | "not_extracted") =>
    totalRows.reduce((sum, row) => sum + (row[key] ?? 0), 0);
  if (run.manifest.data_kind === "synthetic") {
    return "Synthetic test fixtures check expected behavior; this match rate is not production accuracy.";
  }
  return `Extraction rules were tuned on these same public Texas documents. The ${count("matched")} of ${count("matched") + count("mismatched")} comparable matches are an in-sample check, not held-out measured accuracy. ${count("not_comparable")} values are not comparable and ${count("not_extracted")} were not extracted; both are counted separately in the table.`;
}

export function Trust({ run }: { run: Run }) {
  const mismatches = run.validation.filter((result) => result.verdict === "mismatch");
  return (
    <div className="report-page">
      <header className="page-header">
        <RunEyebrow run={run} />
        <h1 className="page-title">Which values can a broker quote?</h1>
        <dl aria-label="What these numbers describe" className="trust-context grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          <dt className={MUTED}>Data kind</dt><dd>{dataKindText(run)}</dd>
          <dt className={MUTED}>Slice</dt><dd className="tabular-nums">{sliceText(run)}</dd>
          <dt className={MUTED}>As of</dt><dd className="tabular-nums">{asOf(run)}, run {run.manifest.run_id}</dd>
          <dt className={MUTED}>Confidence floor</dt>
          <dd>A value read with confidence below {run.manifest.config.confidence_floor} never decides a change flag.</dd>
        </dl>
      </header>
      <section aria-labelledby="accuracy-heading" tabIndex={0} className={cn(CARD, "overflow-x-auto")}>
        <h2 id="accuracy-heading" className="panel-title">PDF values checked against CMS</h2>
        <p className="panel-note">
          {accuracyScope(run)} Match rate counts only values both sides state comparably. Not comparable, not extracted, and not in CMS are counted apart.
        </p>
        {run.manifest.data_kind === "public" && (
          <p className="panel-note">
            CMS reports the OTC allowance on a shared card. An OTC match confirms the shared-card figure, not an OTC-only balance.
          </p>
        )}
        <table aria-labelledby="accuracy-heading" className={cn(TABLE, "min-w-[860px]")}>
          <thead>
            <tr>
              <th scope="col" className={TH}>Field</th>
              <th scope="col" className={TH}>Method</th>
              {COUNTS.map(([key, label]) => <th key={key} scope="col" className={cn(TH, "text-right")}>{label}</th>)}
              <th scope="col" className={cn(TH, "text-right")}>Match rate</th>
            </tr>
          </thead>
          <tbody>
            {run.accuracy.rows.map((row) => (
              <tr key={accuracyLabel(row)} aria-label={accuracyLabel(row)} className={row.field ? undefined : "font-semibold"}>
                <th scope="row" className={cn(TD, "font-medium")}>{row.field ? fieldLabel(row.field) : "All fields"}</th>
                <td className={TD}>{methodText(row.method)}</td>
                {COUNTS.map(([key]) => <td key={key} className={cn(TD, "text-right")}>{row[key] ?? 0}</td>)}
                <td className={cn(TD, "text-right")}>{matchRateText(row)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section aria-labelledby="mismatch-heading" className={cn(CARD, "review-panel")}>
        <h2 id="mismatch-heading" className="text-sm font-semibold">Where the PDF and CMS disagree</h2>
        {mismatches.length === 0 ? (
          <p className="mt-1 text-sm">No disagreements in this run.</p>
        ) : (
          <ul className="mt-2 space-y-3 text-sm">
            {mismatches.map((m) => (
              <li key={`${m.plan_id} ${m.year} ${m.field}`} aria-label={`${fieldLabel(m.field)}, ${m.plan_id} ${m.year}`}>
                <p className="font-medium">{fieldLabel(m.field)}, <span className="font-mono">{m.plan_id}</span> {m.year}</p>
                <p>
                  PDF says {fieldValueText(m.pdf_value, m.pdf_unit)}{" "}
                  {m.pdf_citation && <CitationText citation={m.pdf_citation} manifest={run.manifest} />}
                </p>
                <p>
                  CMS says {fieldValueText(m.cms_value, m.cms_unit)}{" "}
                  {m.cms_citation && <CitationText citation={m.cms_citation} manifest={run.manifest} />}
                </p>
                <p className={MUTED}>Neither value is picked. Check the page before quoting.</p>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="queue-heading" className={cn(CARD, "review-panel")}>
        <h2 id="queue-heading" className="text-sm font-semibold">Review queue ({run.reviewQueue.length})</h2>
        {reviewGroups(run.reviewQueue).map(({ severity, count, kinds }) => (
          <div key={severity} className="mt-3 space-y-2">
            <h3 className="flex items-center gap-2 text-sm font-semibold">
              <SeverityBadge tone={SEVERITY_TONE[severity]} label={sentence(severity)} /> {count}
            </h3>
            {kinds.map(({ kind, items }) => (
              <div key={kind} role="group" aria-label={`${sentence(severity)}: ${reviewKindText(kind)}`} className="space-y-1 pl-2 text-sm">
                <p className="font-medium">{reviewKindText(kind)} ({items.length})</p>
                <p className={MUTED}>{REVIEW_EXPLANATIONS[kind] ?? "A person should check this value."}</p>
                <ul className="list-disc space-y-1 pl-5">
                  {items.map((item, i) => (
                    <li key={i}>
                      <span className="font-mono">{item.plan_id ?? "No plan"}</span>
                      {[item.field && fieldLabel(item.field), item.year].filter(Boolean).map((part) => `, ${part}`)}: {item.reason}{" "}
                      {item.evidence.map((citation, j) => (
                        <span key={j} className="mr-2"><CitationText citation={citation} manifest={run.manifest} /></span>
                      ))}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ))}
      </section>
    </div>
  );
}
