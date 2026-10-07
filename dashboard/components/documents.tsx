import { RunEyebrow } from "@/components/run-eyebrow";
import { CARD } from "@/components/tiles";
import type { Run } from "@/lib/run-loader";
import { documentRows, noLinkText } from "@/lib/trust";
import { cn } from "@/lib/utils";

const MUTED = "text-xs muted";

// The carrier PDF is never served, embedded, or proxied here. A link goes only to the carrier's own
// https URL as recorded in the run, in a new tab.
function CarrierLink({ url, page }: { url: string; page?: number }) {
  const href = page === undefined ? url : `${url.split("#")[0]}#page=${page}`;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="underline">
      Open the carrier&apos;s page{page === undefined ? "" : ` ${page}`}
    </a>
  );
}

export function Documents({ run }: { run: Run }) {
  const rows = documentRows(run);
  return (
    <div className="report-page">
      <header className="page-header">
        <RunEyebrow run={run} />
        <h1 className="page-title">Show me the page.</h1>
        <p className="page-context">
          Every document run {run.manifest.run_id} read, and the page each value came from. No PDF is stored in or served
          from this site.
        </p>
      </header>
      {rows.map((row) => (
        <section key={row.id} aria-label={row.id} className={cn(CARD, "document-panel space-y-2 text-sm")}>
          <h2 className="font-mono font-semibold break-all">{row.id}</h2>
          <dl className="grid gap-x-4 gap-y-0.5 sm:grid-cols-[auto_1fr]">
            <dt className={MUTED}>Carrier</dt><dd>{row.carrier}</dd>
            <dt className={MUTED}>Plan</dt><dd>{row.plan}</dd>
            <dt className={MUTED}>Year</dt><dd className="tabular-nums">{row.year ?? "Not identified"}</dd>
          </dl>
          <details className="technical-details">
            <summary>Document technical details</summary>
            <dl className="grid gap-x-4 gap-y-0.5 sm:grid-cols-[auto_1fr]">
              <dt className={MUTED}>Type</dt><dd>{row.input.document_type ?? "Not identified"}</dd>
              <dt className={MUTED}>Pages</dt><dd className="tabular-nums">{row.input.page_count ?? "Not known"}</dd>
              <dt className={MUTED}>SHA-256</dt><dd className="font-mono text-xs break-all">{row.input.sha256}</dd>
            </dl>
          </details>
          {row.status && <p>{row.status}</p>}
          <p>{row.url ? <CarrierLink url={row.url} /> : <span className={MUTED}>{noLinkText(run)}</span>}</p>
          {row.values.length > 0 && (
            <ul aria-label={`Values cited from ${row.id}`} className="document-values grid gap-x-6 gap-y-2 sm:grid-cols-2">
              {row.values.map(({ field, label, page }) => (
                <li key={field} className="tabular-nums">
                  {label}, page {page}
                  {row.url && <span className="ml-2 text-xs"><CarrierLink url={row.url} page={page} /></span>}
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}
