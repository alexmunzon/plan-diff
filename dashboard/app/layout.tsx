import type { Metadata } from "next";

import { RunNav } from "@/components/run-nav";
import { ThemeToggle } from "@/components/theme-toggle";
import "./globals.css";

export const metadata: Metadata = {
  title: "plan-diff",
  description:
    "Compare Medicare Advantage plan changes for broker review. Carrier documents compared year over year, every value cited to its page. Public data only; not suitability recommendations.",
};

// Runs before the first paint, so a dark page never flashes white. The saved choice wins;
// without one (or with storage blocked) the system setting decides. Copied from agency-intake-kit.
const THEME_SCRIPT = `(function(){var d=null;try{var t=localStorage.getItem("theme");if(t==="dark"||t==="light")d=t==="dark"}catch(e){}if(d===null)d=matchMedia("(prefers-color-scheme: dark)").matches;document.documentElement.classList.toggle("dark",d)})()`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="app-shell font-sans">
        <a href="#main-content" className="skip-link">Skip to main content</a>
        <nav aria-label="Main" className="app-sidebar">
          <div className="sidebar-brand">
            <div>
              <p className="brand-title">plan-diff <span data-version-badge className="ml-1 inline-block rounded border border-current px-1.5 py-0.5 align-middle text-[10px] font-semibold tracking-wide"><span aria-hidden="true">V2</span><span className="sr-only">Version 2</span></span></p>
              <p className="brand-caption">Data Trust Series</p>
            </div>
            <ThemeToggle />
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
