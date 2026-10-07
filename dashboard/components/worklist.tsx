"use client";
import { useRef, useState } from "react";
import { parseWorklist, type Worklist } from "@/lib/worklist";
export function WorklistView({ initial }: { initial: Worklist }) {
  const [data,setData] = useState(initial), [filter,setFilter] = useState("all"), [search,setSearch] = useState(""), [error,setError] = useState("");
  const generation = useRef(0);
  const items = data.items.filter(i => (filter === "all" || i.state === filter) && `${i.client_id} ${i.policy_id} ${i.reasons.join(" ")}`.toLowerCase().includes(search.toLowerCase()));
  return <section className="space-y-5">
    <header><h1 className="text-2xl font-semibold">Broker review worklist</h1><p className="muted">Synthetic records only. Every item needs broker review. These are not suitability recommendations.</p></header>
    <div className="panel p-4 space-y-3"><p>Run {data.run_id} · {data.agency_id}</p><p>Imported artifact only. Source hashes are recorded, not independently reverified in this browser. Nothing is uploaded or saved.</p>
      <label className="block">Import synthetic worklist JSON <input type="file" accept="application/json,.json" onChange={async e => { const file=e.target.files?.[0]; const id=++generation.current; e.target.value=""; if(!file)return; try { if(file.size>2_000_000)throw Error("Worklist exceeds 2 MB limit"); const next=parseWorklist(await file.text()); if(id===generation.current){setData(next);setError("");setFilter("all");setSearch("");} } catch {if(id===generation.current)setError("Import rejected. Your prior valid worklist is unchanged. Use a synthetic worklist from the integration command.");} }} /></label>
      {error && <p role="alert">{error}</p>}
      <label className="block">Status <select value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All states</option><option value="ready_for_review">Ready for review</option><option value="needs_review">Needs review</option><option value="unsupported">Unsupported</option></select></label>
      <label className="block">Find client, policy or reason <input value={search} onChange={e=>setSearch(e.target.value)} /></label>
      <p role="status">Showing {items.length} of {data.items.length} items · {data.items.filter(i=>i.state==="ready_for_review").length} ready for review + {data.items.filter(i=>i.state==="needs_review").length} needs review + {data.items.filter(i=>i.state==="unsupported").length} unsupported = {data.items.length} total</p>
    </div>
    {items.map(i=><article key={i.item_id} className="panel p-4 space-y-2 break-words"><h2 className="font-semibold">{i.client_id} · {i.policy_id ?? "Missing policy"}</h2><p>{i.state.replaceAll("_"," ")} · Broker review required · Identity: {i.identity_state}</p><ul>{i.reasons.map(r=><li key={r}>{r.replaceAll("_"," ")}</li>)}</ul><p>Plan: {i.coverage?.plan_id ?? "Missing"} · Year: {i.coverage?.plan_year ?? "Missing"} · County: {i.coverage?.county ?? "Missing"}</p>
      {i.coverage && <p>Enrollment evidence: {i.coverage.provenance.source_file}, row {i.coverage.provenance.row_number}; artifact {i.coverage.provenance.artifact}, row {i.coverage.provenance.artifact_row}</p>}
      {i.plan_diff && <details><summary>Plan changes and page evidence</summary><p>Artifact: {i.plan_artifact}</p>{i.plan_diff.changes.map(c=><div key={c.field} className="my-3"><h3>{c.field.replaceAll("_"," ")} · {c.direction}</h3>{(["old","new"] as const).map(side=><p key={side}>{side}: {c[side] ? `${JSON.stringify(c[side].value)} ${c[side].unit ?? "unit missing"} · ${c[side].citation.document_id}, page ${c[side].citation.page}: ${c[side].citation.text ?? "No quote supplied"}` : "Missing evidence"}</p>)}</div>)}{i.plan_diff.evidence.map((c,n)=><p key={n}>Crosswalk: {c.document_id}, page {c.page}: {c.text}</p>)}</details>}
    </article>)}
    {!items.length && <p>No items match. Clear filters to view the full inventory.</p>}
    <details className="panel p-4"><summary>Upstream issues ({data.issues.length})</summary>{data.issues.map((i,n)=><p key={n}>{i.code} · {i.artifact ?? "No artifact"} {i.artifact_row ?? ""}</p>)}</details>
  </section>;
}
