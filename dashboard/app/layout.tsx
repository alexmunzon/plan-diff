import type { Metadata } from "next";

import { RunNav } from "@/components/run-nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "plan-diff",
  description:
    "Which Medicare Advantage plans changed enough that a client should shop again? Carrier documents compared year over year, every value cited to its page. Public data only.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="app-shell font-sans">
        <a href="#main-content" className="skip-link">Skip to main content</a>
        <nav aria-label="Main" className="app-sidebar">
          <div className="sidebar-brand">
            <div>
              <p className="brand-title">plan-diff</p>
              <p className="brand-caption">Data Trust Series</p>
            </div>
          </div>
          <RunNav />
        </nav>
        <main id="main-content" tabIndex={-1} className="app-main">
          <aside aria-label="Review scope" className="panel mb-6 p-4 text-sm muted">
            Review the selected run&apos;s evidence. Plan changes are review signals; a client worklist needs separately supplied enrollment evidence. Browser review labels are not authenticated approval.
          </aside>
          {children}
        </main>
      </body>
    </html>
  );
}
