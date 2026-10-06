import { render, screen, within } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { Changes } from "@/components/changes";
import { Documents } from "@/components/documents";
import { Overview } from "@/components/overview";
import { PlanComparison } from "@/components/plan-comparison";
import { RunNav } from "@/components/run-nav";
import { Trust } from "@/components/trust";
import { diffFor, planIds } from "@/lib/compare";
import { loadRunDir, TEXAS_RUN_DIR } from "@/lib/run-dir";
import { DEMO, pageHref, runForPath, TEXAS } from "@/lib/runs";

const path = vi.hoisted(() => ({ current: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => path.current }));

describe("runs", () => {
  it("keeps the demo the default and puts the real run under /texas", () => {
    expect(runForPath("/")).toBe(DEMO);
    expect(runForPath("/plans/H9999-001")).toBe(DEMO);
    expect(runForPath("/texasish")).toBe(DEMO);
    expect(runForPath("/texas")).toBe(TEXAS);
    expect(runForPath("/texas/plans/H0028-030")).toBe(TEXAS);
    expect(pageHref(DEMO, "/")).toBe("/");
    expect(pageHref(TEXAS, "/")).toBe("/texas");
    expect(pageHref(TEXAS, "/trust")).toBe("/texas/trust");
  });

  it("the nav follows the run you are in and marks only the current page", () => {
    path.current = "/texas/trust";
    render(<RunNav />);
    expect(screen.getByRole("link", { name: "Texas 2026 to 2027 (public)" })).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("link", { name: "Demo run (synthetic)" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Trust" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Trust" })).toHaveAttribute("href", "/texas/trust");
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
  });
});

describe("Texas run", () => {
  it("loads as public data with a carrier https link for every PDF", async () => {
    const run = await loadRunDir(TEXAS_RUN_DIR);
    expect(run.manifest.data_kind).toBe("public");
    const pdfs = run.manifest.inputs.filter((i) => i.kind === "pdf");
    expect(pdfs).toHaveLength(12);
    for (const input of pdfs) expect(input.source_url).toMatch(/^https:\/\//);
    expect(planIds(run)).toEqual(["H0028-030", "H5294-014"]);
  });

  it("answers the first-screen question with both plans flagged and links inside /texas", async () => {
    render(<Overview run={await loadRunDir(TEXAS_RUN_DIR)} base={TEXAS.base} />);
    const rows = screen.getAllByRole("listitem", { name: /^Plan / });
    expect(rows).toHaveLength(2);
    const humana = within(screen.getByRole("listitem", { name: "Plan H0028-030" }));
    expect(humana.getByText("Yes")).toBeInTheDocument();
    expect(humana.getByRole("link", { name: "H0028-030" })).toHaveAttribute("href", "/texas/plans/H0028-030");
  });

  it("explains public accuracy scope and the shared OTC card limitation on Trust", async () => {
    render(<Trust run={await loadRunDir(TEXAS_RUN_DIR)} />);
    expect(screen.getByText(/Extraction rules were tuned on these same public Texas documents/)).toBeInTheDocument();
    expect(screen.getByText(/48 of 48 comparable matches are an in-sample check, not held-out measured accuracy/)).toBeInTheDocument();
    expect(screen.getByText(/2 values are not comparable and 10 were not extracted/)).toBeInTheDocument();
    expect(screen.getByText(/CMS reports the OTC allowance on a shared card/)).toBeInTheDocument();
    expect(screen.getByText(/not an OTC-only balance/)).toBeInTheDocument();
  });

  it("no page links to a PDF on this site; carrier links are https", async () => {
    const run = await loadRunDir(TEXAS_RUN_DIR);
    const pages = [
      <Overview key="o" run={run} base={TEXAS.base} />,
      <Changes key="c" run={run} base={TEXAS.base} />,
      <Trust key="t" run={run} />,
      <Documents key="d" run={run} />,
      ...planIds(run).map((plan) => <PlanComparison key={plan} run={run} diff={diffFor(run, plan)!} />),
    ];
    const hrefs = pages.flatMap((page) => [...renderToStaticMarkup(page).matchAll(/href="([^"]*)"/g)].map((m) => m[1]));
    expect(hrefs.some((href) => href.startsWith("https://assets.humana.com/"))).toBe(true);
    for (const href of hrefs) {
      const url = new URL(href.replaceAll("&amp;", "&"), "https://plan-diff.site/");
      const inside = url.host === "plan-diff.site";
      expect(inside && /\.pdf/i.test(url.pathname), href).toBe(false);
      expect(inside ? url.pathname.startsWith("/texas/") : url.protocol === "https:", href).toBe(true);
    }
  });
});
