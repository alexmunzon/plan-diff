import { readFile } from "node:fs/promises";
import path from "node:path";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import RunError from "@/app/error";
import NotFound from "@/app/not-found";
import { PlanComparison } from "@/components/plan-comparison";
import { RunNav } from "@/components/run-nav";
import { diffFor } from "@/lib/compare";
import { loadRunDir, TEXAS_RUN_DIR } from "@/lib/run-dir";

vi.mock("next/navigation", () => ({ usePathname: () => "/texas/trust" }));

describe("recruiting demo acceptance", () => {
  it("links the other two builds and downloads this run's inspectable evidence", async () => {
    render(<RunNav />);
    expect(screen.getByRole("link", { name: "1. Intake Kit" })).toHaveAttribute("href", "https://agency-intake-kit.vercel.app");
    expect(screen.getByRole("link", { name: "2. Bob Resolve" })).toHaveAttribute("href", "https://bob-resolve-nine.vercel.app");
    fireEvent.click(screen.getByText("Download technical evidence"));
    for (const [label, file] of [["Manifest JSON", "manifest.json"], ["Accuracy JSON", "accuracy.json"], ["Review queue JSONL", "review_queue.jsonl"]]) {
      const link = screen.getByRole("link", { name: label });
      expect(link).toHaveAttribute("href", `/texas-run/${file}`);
      expect(link).toHaveAttribute("download");
      expect(await readFile(path.join(TEXAS_RUN_DIR, file), "utf8")).not.toBe("");
    }
  });

  it("keeps missing public drug values distinct from a cited zero premium", async () => {
    const run = await loadRunDir(TEXAS_RUN_DIR);
    render(<PlanComparison run={run} diff={diffFor(run, "H5294-014")!} />);
    const drug = within(screen.getByRole("row", { name: "Drug deductible" }));
    expect(drug.getAllByText("Not found in the document")).toHaveLength(2);
    expect(drug.queryByText(/\$0/)).not.toBeInTheDocument();
    const premium = within(screen.getByRole("row", { name: "Monthly premium" }));
    expect(premium.getAllByText("$0.00 a month")).toHaveLength(2);
    for (const link of premium.getAllByRole("link")) expect(link.getAttribute("href")).toMatch(/^https:.*#page=4$/);
    expect(screen.getByText(/Service area lost 33 counties/)).toBeInTheDocument();
  });

  it("offers recovery without exposing an internal run failure", () => {
    const retry = vi.fn();
    render(<RunError error={new Error("/private/run/file.json")} retry={retry} />);
    expect(screen.getByRole("heading", { name: "This run could not be loaded" })).toBeInTheDocument();
    expect(screen.queryByText(/private/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("gives unknown URLs a route back to either run", () => {
    render(<NotFound />);
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Synthetic demo" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Public Texas run" })).toHaveAttribute("href", "/texas");
  });
});
