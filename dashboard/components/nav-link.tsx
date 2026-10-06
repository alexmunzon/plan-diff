"use client";
// Adapted from agency-intake-kit dashboard/components/nav-link.tsx at a54faee: adds pages not built yet.

import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const ITEM = "nav-item";

// Only the page you are on is highlighted and announced as the current page. A page with no href
// is not built yet: it shows as plain gray text that says so, and is not a link.
export function NavLink({ href, label, exact = false, icon: Icon }: { href?: string; label: string; exact?: boolean; icon?: LucideIcon }) {
  const pathname = usePathname();
  if (!href) {
    return (
      <span aria-disabled="true" className={cn(ITEM, "nav-item-disabled")}>
        {label} <span className="text-xs">(coming soon)</span>
      </span>
    );
  }
  // A plan page counts as the Plan comparison page.
  // PR 15: a run's overview ("/texas") is exact, so its other pages do not highlight it too.
  const current = pathname === href || (!exact && href !== "/" && pathname.startsWith(`${href}/`));
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={cn(
        ITEM,
        current && "nav-item-current",
      )}
    >
      {Icon && <Icon aria-hidden className="size-4 shrink-0" />}
      {label}
    </Link>
  );
}
