import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Overview } from "@/components/overview";
import { DEMO_RUN_DIR, TEXAS_RUN_DIR, loadRunDir } from "@/lib/run-dir";
import { TEXAS } from "@/lib/runs";

async function show() {
  render(<Overview run={await loadRunDir(DEMO_RUN_DIR)} />);
}

const tile = (label: string) => within(screen.getByRole("group", { name: label }));

describe("Overview", () => {
  it("asks the first-screen question", async () => {
    await show();
    expect(
      screen.getByRole("heading", { level: 1, name: "Which plan changes need broker review?" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Flags are not suitability recommendations/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Compare plan changes" })).toHaveClass("action-primary");
    expect(screen.getByRole("link", { name: "Review evidence" })).not.toHaveClass("action-primary");
  });

  it("shows flagged plans first, then the undecided one, each with reasons and status", async () => {
    await show();
    const rows = screen.getAllByRole("listitem", { name: /^Plan / });
    expect(rows.map((row) => row.getAttribute("aria-label"))).toEqual([
      "Plan H9999-001",
      "Plan H9999-002",
      "Plan H9999-003",
      "Plan H9999-004",
    ]);
    const first = within(rows[0]);
    expect(first.getByText("Flagged for review")).toBeInTheDocument();
    expect(first.getByText("Premium up $25 a month")).toBeInTheDocument();
    expect(first.getByText("Renews as H9999-001")).toBeInTheDocument();
    expect(first.getByText("5 review items")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Plan consolidated into H9999-001")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Plan terminated")).toBeInTheDocument();
    expect(within(rows[2]).getByText("No review items")).toBeInTheDocument();
  });

  it("shows undecided as text, never as no, with the reason it is undecided", async () => {
    await show();
    const last = within(screen.getByRole("listitem", { name: "Plan H9999-004" }));
    expect(last.getByText("Undecided, needs review")).toBeInTheDocument();
    expect(last.queryByText("No change flag")).not.toBeInTheDocument();
    expect(last.getByText("Maximum out-of-pocket change flag needs review: 2027 value read with confidence 0.6, below 0.7")).toBeVisible();
    const original = last.getByText("maximum out-of-pocket cannot decide shop again: 2027 value read with confidence 0.6, below 0.7");
    expect(original).not.toBeVisible();
    const disclosure = last.getByText("Original recorded reason");
    disclosure.focus();
    expect(disclosure).toHaveFocus();
    fireEvent.click(disclosure);
    expect(original).toBeVisible();
    fireEvent.click(disclosure);
    expect(original).not.toBeVisible();
  });

  it("keeps technical metrics collapsed, with synthetic caveats when opened repeatedly", async () => {
    await show();
    expect(tile("Plans compared").getByText("4")).toBeInTheDocument();
    expect(tile("Flagged for review").getByText("3")).toBeInTheDocument();
    expect(tile("Undecided").getByText("1")).toBeInTheDocument();
    expect(tile("Review items").getByText("10")).toBeInTheDocument();
    const toggle = screen.getByText("Run technical details");
    const details = toggle.closest("details")!;
    expect(details).not.toHaveAttribute("open");
    expect(screen.getByText("97.6%")).not.toBeVisible();
    expect(screen.getByText(/Jev off, 0 calls, \$0\.00/)).not.toBeVisible();
    toggle.focus();
    expect(toggle).toHaveFocus();
    fireEvent.click(toggle);
    expect(tile("Accuracy match rate").getByText("97.6%")).toBeInTheDocument();
    expect(tile("Accuracy match rate").getByText(/on synthetic fixtures/)).toBeInTheDocument();
    expect(screen.getByText(/Jev off, 0 calls, \$0\.00/)).toBeVisible();
    fireEvent.click(toggle);
    expect(details).not.toHaveAttribute("open");
    fireEvent.click(toggle);
    expect(screen.getByText("97.6%")).toBeVisible();
    expect(screen.getByRole("listitem", { name: "Plan H9999-001" }).closest("details")).toBeNull();
  });

  it("labels the public Texas match count as in-sample and separates unmeasured values", async () => {
    render(<Overview run={await loadRunDir(TEXAS_RUN_DIR)} base={TEXAS.base} />);
    fireEvent.click(screen.getByText("Run technical details"));
    const accuracy = tile("Accuracy match rate");
    expect(accuracy.getByText("100.0%")).toBeInTheDocument();
    expect(accuracy.getByText(/48 of 48 comparable values, across 2 public plans/)).toBeInTheDocument();
    expect(accuracy.getByText(/tuned on these same documents, not held-out measured accuracy/i)).toBeInTheDocument();
    expect(accuracy.getByText(/2 values not comparable and 10 values not extracted/)).toBeInTheDocument();
    expect(screen.getByText(/Public Texas carrier documents and CMS files/)).toBeInTheDocument();
  });
});
