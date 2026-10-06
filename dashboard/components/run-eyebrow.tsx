import type { Run } from "@/lib/run-loader";

/** Keep public and synthetic provenance visible on every evidence surface. */
export function RunEyebrow({ run }: { run: Run }) {
  return (
    <p className="report-eyebrow">
      <span className="run-provenance">{run.manifest.data_kind === "synthetic" ? "Synthetic demo" : "Public Texas run"}</span>
      <span>Plan-year review</span>
      <span className="tabular-nums">{run.manifest.years.join(" to ")}</span>
    </p>
  );
}
