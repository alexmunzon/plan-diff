"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NavLink } from "@/components/nav-link";
import { pageHref, RUNS, runForPath } from "@/lib/runs";
import { cn } from "@/lib/utils";

const PAGES: { label: string; page: string }[] = [
  { label: "Overview", page: "/" },
  { label: "Plan comparison", page: "/plans" },
  { label: "Changes", page: "/changes" },
  { label: "Trust", page: "/trust" },
  { label: "Documents", page: "/documents" },
];

// PR 15: pick a run, then a page in that run. The demo stays the default; the page links follow
// the run you are in, so the Texas pages never jump back to the demo.
export function RunNav() {
  const current = runForPath(usePathname());
  return (
    <>
      <ul aria-label="Run" className="flex gap-1 overflow-x-auto px-2 pb-2 text-xs lg:flex-col lg:px-3">
        {RUNS.map((run) => (
          <li key={run.id} className="shrink-0">
            <Link
              href={pageHref(run, "/")}
              aria-current={run.id === current.id ? "true" : undefined}
              className={cn(
                "block rounded-md border px-3 py-1",
                run.id === current.id
                  ? "border-indigo-300 bg-indigo-50 font-medium text-indigo-700 dark:border-indigo-800 dark:bg-indigo-950 dark:text-indigo-300"
                  : "border-transparent text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800",
              )}
            >
              {run.label}
            </Link>
          </li>
        ))}
      </ul>
      <ul className="flex gap-1 overflow-x-auto px-2 pb-2 text-sm lg:flex-col lg:px-3">
        {PAGES.map(({ label, page }) => (
          <li key={label} className="shrink-0">
            <NavLink href={pageHref(current, page)} label={label} exact={page === "/"} />
          </li>
        ))}
      </ul>
    </>
  );
}
