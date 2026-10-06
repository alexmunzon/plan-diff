"use client";

import { ArrowLeftRight, Columns3, Download, FileText, LayoutDashboard, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { NavLink } from "@/components/nav-link";
import { pageHref, RUNS, runForPath } from "@/lib/runs";
import { cn } from "@/lib/utils";

const PAGES = [
  { label: "Overview", page: "/", icon: LayoutDashboard },
  { label: "Plan comparison", page: "/plans", icon: Columns3 },
  { label: "Changes", page: "/changes", icon: ArrowLeftRight },
  { label: "Trust", page: "/trust", icon: ShieldCheck },
  { label: "Documents", page: "/documents", icon: FileText },
];

// PR 15: pick a run, then a page in that run. The demo stays the default; the page links follow
// the run you are in, so the Texas pages never jump back to the demo.
export function RunNav() {
  const current = runForPath(usePathname());
  return (
    <>
      <p className="sidebar-label">Select a run</p>
      <ul aria-label="Run" className="run-switch">
        {RUNS.map((run) => (
          <li key={run.id} className="shrink-0">
            <Link
              href={pageHref(run, "/")}
              aria-current={run.id === current.id ? "true" : undefined}
              className={cn(
                "run-option",
                run.id === current.id
                  ? "run-option-current"
                  : undefined,
              )}
            >
              {run.label}
            </Link>
          </li>
        ))}
      </ul>
      <ul aria-label="Pages" className="page-navigation">
        {PAGES.map(({ label, page, icon }) => (
          <li key={label} className="shrink-0">
            <NavLink href={pageHref(current, page)} label={label} icon={icon} exact={page === "/"} />
          </li>
        ))}
      </ul>
      <div className="sidebar-support">
        <section aria-label="Run evidence" className="sidebar-section">
          <h2 className="font-medium">Download run evidence</h2>
          <p className="mt-2">{current.label}. JSON only, no PDFs.</p>
          <ul className="sidebar-links">
            {[["Manifest JSON", "manifest.json"], ["Accuracy JSON", "accuracy.json"], ["Review queue JSONL", "review_queue.jsonl"]].map(([label, file]) => (
              <li key={file}><a className="flex items-center gap-2 underline" href={`/${current.folder}/${file}`} download><Download aria-hidden className="size-3" />{label}</a></li>
            ))}
          </ul>
        </section>
        <section aria-label="Agency Data Trust Series" className="sidebar-section">
          <h2 className="font-medium">Agency Data Trust Series</h2>
          <p className="mt-2">Separate demos, shared trust principles.</p>
          <ul className="sidebar-links">
            <li><a className="underline" href="https://agency-intake-kit.vercel.app">1. Intake Kit</a></li>
            <li><a className="underline" href="https://bob-resolve-nine.vercel.app">2. Bob Resolve</a></li>
            <li aria-current="true">3. Plan Diff</li>
          </ul>
        </section>
      </div>
    </>
  );
}
