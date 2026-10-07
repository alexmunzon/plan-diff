import { render, screen, within } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Changes } from "@/components/changes";
import { Documents } from "@/components/documents";
import { Overview } from "@/components/overview";
import { PlanComparison } from "@/components/plan-comparison";
import { Trust } from "@/components/trust";
import { diffFor, planIds } from "@/lib/compare";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";
import type { Run } from "@/lib/run-loader";
import { documentRows } from "@/lib/trust";

async function demo(change?: (run: Run) => void) {
  const run = await loadRunDir(DEMO_RUN_DIR);
  change?.(run);
  return run;
}

const cells = (label: string) => within(screen.getByRole("row", { name: label })).getAllByRole("cell").map((c) => c.textContent);

describe("Trust", () => {
  it("labels the numbers and counts not comparable apart from mismatched", async () => {
    render(<Trust run={await demo()} />);
    expect(screen.getByRole("heading", { level: 1, name: "Which values can a broker quote?" })).toBeInTheDocument();
    const labels = within(screen.getByLabelText("What these numbers describe"));
    expect(labels.getByText("Synthetic test fixtures")).toBeInTheDocument();
    expect(labels.getByText("Plans H9999-001, H9999-002, H9999-003, H9999-004; plan years 2026 and 2027")).toBeInTheDocument();
    expect(labels.getByText("2026-10-05, run demo")).toBeInTheDocument();
    // Rules, matched, mismatched, not comparable, not extracted, not in CMS, match rate
    expect(cells("Dental allowance, Rules")).toEqual(["Rules", "0", "0", "3", "0", "3", "No comparable values"]);
    expect(cells("Specialist visit, Rules")).toEqual(["Rules", "2", "1", "0", "0", "3", "66.7% (2 of 3)"]);
    expect(cells("All fields, Rules")).toEqual(["Rules", "41", "1", "6", "0", "42", "97.6% (41 of 42)"]);
  });

  it("example 4: the planted specialist mismatch shows $45 and $40 with both citations", async () => {
    render(<Trust run={await demo()} />);
    const item = within(screen.getByRole("listitem", { name: "Specialist visit, H9999-001 2026" }));
    expect(item.getByText(/PDF says \$45\.00 copay a visit/)).toBeInTheDocument();
    expect(item.getByText(/CMS says \$40\.00 copay a visit/)).toBeInTheDocument();
    expect(item.getByText("H9999-001_2026_SB, page 1")).toBeInTheDocument();
    expect(item.getByText("CMS file pbp_b7_health_prof.txt, row 1")).toBeInTheDocument();
  });

  it("groups the review queue by severity and kind, each kind explained", async () => {
    render(<Trust run={await demo()} />);
    expect(screen.getByRole("heading", { name: "Review queue (10)" })).toBeInTheDocument();
    const high = within(screen.getByRole("group", { name: "High: Cannot decide shop again" }));
    expect(high.getByText(/left undecided instead of guessed/)).toBeInTheDocument();
    const notComparable = within(screen.getByRole("group", { name: "Medium: Cannot be checked against CMS" }));
    expect(notComparable.getAllByRole("listitem")).toHaveLength(6);
    expect(screen.getByRole("group", { name: "Low: Two values in one cell" })).toBeInTheDocument();
  });

  it("shows the confidence floor the run recorded, not a copy", async () => {
    const run = await demo((r) => {
      r.manifest.config.confidence_floor = 0.5;
    });
    render(<Trust run={run} />);
    expect(screen.getByText("A value read with confidence below 0.5 never decides shop again.")).toBeInTheDocument();
    render(<PlanComparison run={run} diff={diffFor(run, "H9999-004")!} />);
    expect(screen.queryByText(/Read with confidence 0.6/)).not.toBeInTheDocument(); // 0.6 is above 0.5
  });
});

describe("Documents", () => {
  it("keeps review status and page evidence outside a keyboard-focusable technical disclosure", async () => {
    render(<Documents run={await demo()} />);
    const region = screen.getByRole("region", { name: "H9999-001_2026_SB" });
    const summary = within(region).getByText("Document technical details");
    expect(summary.tagName).toBe("SUMMARY");
    const details = summary.closest("details")!;
    expect(details).not.toHaveAttribute("open");
    summary.focus();
    expect(summary).toHaveFocus();
    expect(within(details).getByText(/^05038d3690dc/)).toBeInTheDocument();
    expect(within(region).getByText("Specialist visit, page 1").closest("details")).toBeNull();
    const status = screen.getByText("Not identified, in the review queue; no values used");
    expect(status.closest("details")).toBeNull();
    details.open = true;
    expect(details).toHaveAttribute("open");
    expect(within(region).getByText("Dental allowance, page 2").closest("details")).toBeNull();
  });

  it("lists every document with its values and the synthetic note, never a link", async () => {
    render(<Documents run={await demo()} />);
    expect(screen.getByRole("heading", { level: 1, name: "Show me the page." })).toBeInTheDocument();
    const gold = within(screen.getByRole("region", { name: "H9999-001_2026_SB" }));
    expect(gold.getByText("Example Health Plan")).toBeInTheDocument();
    expect(gold.getByText("H9999-001, Synthetic Gold HMO")).toBeInTheDocument();
    expect(gold.getByText("Specialist visit, page 1")).toBeInTheDocument();
    expect(gold.getByText("Dental allowance, page 2")).toBeInTheDocument();
    expect(gold.getByText(/^05038d3690dc/)).toBeInTheDocument();
    expect(screen.getAllByRole("region")).toHaveLength(7);
    expect(screen.getAllByText("Synthetic test document, generated by the demo; not stored in the repo")).toHaveLength(7);
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    const unlabeled = within(screen.getByRole("region", { name: "unlabeled_2026_SB" }));
    expect(unlabeled.getByText("Not identified, in the review queue; no values used")).toBeInTheDocument();
  });

  it("links to the carrier's own https page in a new tab, and nothing else", async () => {
    const run = await demo((r) => {
      r.manifest.data_kind = "public";
      r.manifest.inputs[0].source_url = "https://carrier.example/sb.pdf";
      r.manifest.inputs[1].source_url = "http://carrier.example/sb.pdf";
      r.manifest.inputs[2].source_url = "/demo-run/x.pdf";
    });
    render(<Documents run={run} />);
    const links = screen.getAllByRole("link");
    const values = documentRows(run)[0].values;
    expect(values.length).toBeGreaterThan(0);
    expect(links.map((a) => a.getAttribute("href"))).toEqual([
      "https://carrier.example/sb.pdf",
      ...values.map(({ page }) => `https://carrier.example/sb.pdf#page=${page}`),
    ]);
    for (const a of links) {
      expect(a).toHaveAttribute("target", "_blank");
      expect(a).toHaveAttribute("rel", "noopener noreferrer");
    }
    expect(screen.getAllByText("No carrier link recorded for this file; it is not stored in the repo")).toHaveLength(6);
  });
});

describe("built pages", () => {
  it("no anchor on any page points at a .pdf path inside the site", async () => {
    const run = await demo((r) => {
      for (const input of r.manifest.inputs) input.source_url = "/demo-run/plan.pdf"; // must never become a link
      r.manifest.inputs[0].source_url = "https://carrier.example/plan.pdf";
    });
    const pages = [
      <Overview key="o" run={run} />,
      <Changes key="c" run={run} />,
      <Trust key="t" run={run} />,
      <Documents key="d" run={run} />,
      ...planIds(run).map((plan) => <PlanComparison key={plan} run={run} diff={diffFor(run, plan)!} />),
    ];
    const hrefs = pages.flatMap((page) => [...renderToStaticMarkup(page).matchAll(/href="([^"]*)"/g)].map((m) => m[1]));
    expect(hrefs.some((href) => href.startsWith("https://carrier.example/"))).toBe(true);
    for (const href of hrefs) {
      const url = new URL(href, "https://plan-diff.site/");
      const inside = url.host === "plan-diff.site";
      expect(inside && /\.pdf/i.test(url.pathname), href).toBe(false);
      expect(inside || url.protocol === "https:", href).toBe(true);
    }
  });
});
