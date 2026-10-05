// PR 15: the dashboard shows two committed runs. The synthetic demo stays the default at "/"; the
// real Texas run (public documents and CMS files) lives under "/texas". Client safe: no file access.
export interface RunChoice {
  id: "demo" | "texas";
  /** URL prefix for this run's pages. The demo has none. */
  base: string;
  label: string;
  /** Folder under public/ that holds the run's JSON. */
  folder: string;
}

export const RUNS: RunChoice[] = [
  { id: "demo", base: "", label: "Demo run (synthetic)", folder: "demo-run" },
  { id: "texas", base: "/texas", label: "Texas 2026 to 2027 (public)", folder: "texas-run" },
];

export const DEMO = RUNS[0];
export const TEXAS = RUNS[1];

/** The run a page belongs to, from its path. Anything outside a run's prefix is the demo. */
export function runForPath(pathname: string): RunChoice {
  return RUNS.find((run) => run.base && (pathname === run.base || pathname.startsWith(`${run.base}/`))) ?? DEMO;
}

/** A page path inside a run: pageHref(TEXAS, "/trust") is "/texas/trust", the overview "/texas". */
export function pageHref(run: RunChoice, page: string): string {
  if (page === "/") return run.base || "/";
  return `${run.base}${page}`;
}
