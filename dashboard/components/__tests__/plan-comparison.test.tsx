import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlanComparison } from "@/components/plan-comparison";
import { diffFor } from "@/lib/compare";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";
import type { Run } from "@/lib/run-loader";

async function show(plan: string, change?: (run: Run) => void) {
  const run = await loadRunDir(DEMO_RUN_DIR);
  change?.(run);
  render(<PlanComparison run={run} diff={diffFor(run, plan)!} />);
}

const row = (label: string) => within(screen.getByRole("row", { name: label }));

describe("Plan comparison", () => {
  it.each([
    ["H9999-004", "Maximum out-of-pocket (in network)", "$3,400 / $5,900"],
    ["H9999-001", "Specialist visit", "$45 per visit"],
  ])("does not present %s uncertain values as confirmed unchanged", async (plan, label, source) => {
    await show(plan);
    const field = row(label);
    expect(field.getByText("Needs review")).toBeInTheDocument();
    expect(field.queryByText("No change")).not.toBeInTheDocument();
    expect(field.getByText(`Source text: ${source}`)).toBeInTheDocument();
    if (plan === "H9999-001") expect(field.getByText(/PDF and CMS disagree; value unconfirmed/)).toBeInTheDocument();
  });

  it("example 1: H9999-001 shows the premium going up $25 with both pages cited", async () => {
    await show("H9999-001");
    expect(
      screen.getByRole("heading", { level: 1, name: "What exactly changed between 2026 and 2027 for this plan?" }),
    ).toBeInTheDocument();
    const premium = row("Monthly premium");
    expect(premium.getByText("$0.00 a month")).toBeInTheDocument();
    expect(premium.getByText("$25.00 a month")).toBeInTheDocument();
    expect(premium.getByText("Up")).toBeInTheDocument();
    expect(premium.getByText("Premium")).toBeInTheDocument();
    expect(premium.getByText("H9999-001_2026_SB, page 1")).toBeInTheDocument();
    expect(premium.getByText("H9999-001_2027_SB, page 1")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(16); // header plus the 15 fields
    const verdict = within(screen.getByRole("region", { name: "Verdict" }));
    expect(verdict.getByText("Yes")).toBeInTheDocument();
    expect(verdict.getByText("Premium up $25 a month")).toBeInTheDocument();
    expect(verdict.getByText("CMS file crosswalk_2027.csv, row 1")).toBeInTheDocument();
  });

  it("example 2: H9999-002 says consolidated, never terminated", async () => {
    await show("H9999-002");
    const verdict = within(screen.getByRole("region", { name: "Verdict" }));
    expect(verdict.getByText("Consolidated into H9999-001")).toBeInTheDocument();
    expect(verdict.getByText("Plan consolidated into H9999-001")).toBeInTheDocument();
    expect(screen.queryByText(/terminated/i)).not.toBeInTheDocument();
  });

  it("undecided H9999-004 says so in words, with the reason and the low confidence value", async () => {
    await show("H9999-004");
    const verdict = within(screen.getByRole("region", { name: "Verdict" }));
    expect(verdict.getByText("Undecided, needs review")).toBeInTheDocument();
    expect(verdict.queryByText("No")).not.toBeInTheDocument();
    expect(verdict.getByText(/Maximum out-of-pocket cannot decide shop again/)).toBeInTheDocument();
    expect(row("Maximum out-of-pocket (in network)").getByText("Read with confidence 0.6, below 0.7")).toBeInTheDocument();
    expect(screen.getAllByText(/Read with confidence/)).toHaveLength(1); // only below the floor
    expect(screen.getByText("Cannot decide shop again")).toBeInTheDocument();
  });

  it("shows not comparable in words and lists the plan's review items", async () => {
    await show("H9999-001", (run) => {
      run.diffs[0].changes[0].direction = "not_comparable";
    });
    expect(row("Monthly premium").getByText("Not comparable")).toBeInTheDocument();
    expect(screen.getAllByText("Cannot be checked against CMS")).toHaveLength(4);
    expect(screen.getByText("PDF and CMS disagree")).toBeInTheDocument();
  });

  it("a terminated plan says so instead of an empty table", async () => {
    await show("H9999-003");
    expect(screen.getByText("No 2027 plan to compare: the plan is terminated.")).toBeInTheDocument();
  });

  it("links a page only to the carrier's https copy, never to a repo file", async () => {
    await show("H9999-001", (run) => {
      const input = run.manifest.inputs.find((i) => i.document_id === "H9999-001_2027_SB")!;
      input.source_url = "https://carrier.example/sb-2027.pdf";
      run.manifest.inputs.find((i) => i.document_id === "H9999-001_2026_SB")!.source_url = "/demo-run/x.pdf";
    });
    const links = screen.getAllByRole("link", { name: "H9999-001_2027_SB, page 1" });
    expect(links[0]).toHaveAttribute("href", "https://carrier.example/sb-2027.pdf#page=1");
    expect(screen.queryByRole("link", { name: /H9999-001_2026_SB/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /CMS file/ })).not.toBeInTheDocument();
  });
});
