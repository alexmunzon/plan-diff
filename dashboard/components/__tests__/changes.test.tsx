import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Changes } from "@/components/changes";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";

const row = (label: string) => within(screen.getByRole("row", { name: label }));

describe("Changes", () => {
  it("includes disputed and ambiguous unchanged values in the review list", async () => {
    render(<Changes run={await loadRunDir(DEMO_RUN_DIR)} />);
    for (const label of ["H9999-004 Maximum out-of-pocket (in network)", "H9999-001 Specialist visit"]) {
      expect(row(label).getByText("Needs review")).toBeInTheDocument();
      expect(row(label).queryByText("No change")).not.toBeInTheDocument();
    }
  });

  it("counts every field by category and direction across plans", async () => {
    render(<Changes run={await loadRunDir(DEMO_RUN_DIR)} />);
    expect(screen.getByRole("heading", { level: 1, name: "Where are costs moving across plans?" })).toBeInTheDocument();
    // Premium: H9999-001 up, H9999-002 down, H9999-004 the same.
    expect(row("Premium").getAllByRole("cell").map((c) => c.textContent)).toEqual(["1", "1", "1", "0", "0", "0", "0"]);
    expect(row("Copays").getAllByRole("cell").map((c) => c.textContent)).toEqual(["4", "1", "12", "0", "0", "0", "1"]);
  });

  it("lists every change with plan, field, old, new, and direction (example 1)", async () => {
    render(<Changes run={await loadRunDir(DEMO_RUN_DIR)} />);
    const premium = row("H9999-001 Monthly premium");
    expect(premium.getByRole("link", { name: "H9999-001" })).toHaveAttribute("href", "/plans/H9999-001");
    expect(premium.getByText("$0.00 a month")).toBeInTheDocument();
    expect(premium.getByText("$25.00 a month")).toBeInTheDocument();
    expect(premium.getByText("Up")).toBeInTheDocument();
    expect(row("H9999-002 Monthly premium").getByText("now H9999-001")).toBeInTheDocument();
    expect(screen.getByText("Changes and values needing review (17 fields)")).toBeInTheDocument();
  });
});
