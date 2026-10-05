import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Overview } from "@/components/overview";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";

async function show() {
  render(<Overview run={await loadRunDir(DEMO_RUN_DIR)} />);
}

const tile = (label: string) => within(screen.getByRole("group", { name: label }));

describe("Overview", () => {
  it("asks the first-screen question", async () => {
    await show();
    expect(
      screen.getByRole("heading", { level: 1, name: "Which plans changed enough that a client should shop again?" }),
    ).toBeInTheDocument();
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
    expect(first.getByText("Yes")).toBeInTheDocument();
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
    expect(last.queryByText("No")).not.toBeInTheDocument();
    expect(last.getByText(/Maximum out-of-pocket cannot decide shop again/)).toBeInTheDocument();
  });

  it("shows the summary tiles with the accuracy labeled as synthetic", async () => {
    await show();
    expect(tile("Plans compared").getByText("4")).toBeInTheDocument();
    expect(tile("Shop again").getByText("3")).toBeInTheDocument();
    expect(tile("Undecided").getByText("1")).toBeInTheDocument();
    expect(tile("Review items").getByText("10")).toBeInTheDocument();
    expect(tile("Accuracy match rate").getByText("97.6%")).toBeInTheDocument();
    expect(tile("Accuracy match rate").getByText(/on synthetic fixtures/)).toBeInTheDocument();
    expect(screen.getByText(/Jev off, 0 calls, \$0\.00/)).toBeInTheDocument();
  });
});
