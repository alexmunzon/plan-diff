import type { Metadata } from "next";

import { RunNav } from "@/components/run-nav";
import { ThemeToggle } from "@/components/theme-toggle";
import "./globals.css";

export const metadata: Metadata = {
  title: "plan-diff",
  description:
    "Which Medicare Advantage plans changed enough that a client should shop again? Carrier documents compared year over year, every value cited to its page. Public data only.",
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
      <body className="flex min-h-full flex-col bg-slate-50 font-sans text-slate-900 lg:flex-row dark:bg-slate-950 dark:text-slate-100">
        <nav aria-label="Main" className="border-b border-slate-200 bg-white lg:w-60 lg:shrink-0 lg:border-r lg:border-b-0 dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center justify-between gap-2 px-4 pt-3 pb-2 lg:px-5 lg:pt-6">
            <p className="text-sm font-semibold">plan-diff</p>
            <ThemeToggle />
          </div>
          <RunNav />
        </nav>
        <main className="mx-auto w-full max-w-[1120px] min-w-0 px-4 py-6 sm:px-10">{children}</main>
      </body>
    </html>
  );
}
