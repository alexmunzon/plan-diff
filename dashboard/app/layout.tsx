import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "plan-diff",
  description:
    "Carrier benefit documents turned into one plan schema with page citations, then compared year over year. Public data only.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
        {children}
      </body>
    </html>
  );
}
