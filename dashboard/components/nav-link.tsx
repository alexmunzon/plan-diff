"use client";
// Adapted from agency-intake-kit dashboard/components/nav-link.tsx at a54faee: adds pages not built yet.

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const ITEM = "block rounded-md px-3 py-1.5";

// Only the page you are on is highlighted and announced as the current page. A page with no href
// is not built yet: it shows as plain gray text that says so, and is not a link.
export function NavLink({ href, label }: { href?: string; label: string }) {
  const pathname = usePathname();
  if (!href) {
    return (
      <span aria-disabled="true" className={cn(ITEM, "text-slate-500 dark:text-slate-400")}>
        {label} <span className="text-xs">(coming soon)</span>
      </span>
    );
  }
  // A plan page counts as the Plan comparison page.
  const current = pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={cn(
        ITEM,
        "focus-visible:outline-2 focus-visible:outline-indigo-600",
        current ? "bg-indigo-50 font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300" : "text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
      )}
    >
      {label}
    </Link>
  );
}
