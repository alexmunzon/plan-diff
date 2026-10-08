import { render, screen, within } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import RootLayout, { metadata } from "@/app/layout";
import { ReviewReason } from "@/components/review-reason";
import { RunNav } from "@/components/run-nav";
import { Trust } from "@/components/trust";
import { DEMO_RUN_DIR, loadRunDir, TEXAS_RUN_DIR } from "@/lib/run-dir";

const path = vi.hoisted(() => ({ current: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => path.current }));

it("names Plan Diff and places the theme control after navigation and series links", () => {
  const doc = new DOMParser().parseFromString(renderToStaticMarkup(
    <RootLayout params={Promise.resolve({})}>page</RootLayout>,
  ), "text/html");
  expect(metadata.title).toBe("Plan Diff");
  expect(doc.querySelector(".brand-title")?.textContent).toBe("Plan Diff V2Version 2");
  const sidebar = doc.querySelector(".app-sidebar")!;
  expect(sidebar.lastElementChild?.classList.contains("sidebar-footer")).toBe(true);
  expect(sidebar.lastElementChild?.querySelector("button")?.textContent).toBe("Dark mode");
  expect(doc.querySelector(".sidebar-brand button")).toBeNull();
  expect(doc.querySelector('a[href="https://agency-intake-kit.vercel.app"]')?.textContent).toBe("1. Agency Intake Kit");
});

it("treats Broker worklist as a current nav item and follows repeated route changes", () => {
  path.current = "/worklist";
  const { rerender } = render(<RunNav />);
  const worklist = () => screen.getByRole("link", { name: "Broker worklist (synthetic)" });
  expect(worklist()).toHaveAttribute("href", "/worklist");
  expect(worklist()).toHaveAttribute("aria-current", "page");
  expect(worklist()).toHaveClass("nav-item", "nav-item-current");
  expect(worklist().querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  worklist().focus();
  expect(worklist()).toHaveFocus();
  for (const next of ["/texas/trust", "/plans/H9999-004", "/worklist"]) {
    path.current = next;
    rerender(<RunNav />);
    expect(screen.getAllByRole("link").filter(link => link.getAttribute("aria-current") === "page")).toHaveLength(1);
    if (next !== "/worklist") expect(worklist()).not.toHaveClass("nav-item-current");
  }
  expect(worklist()).toHaveAttribute("aria-current", "page");
});

describe("display-only review explanations", () => {
  it.each([
    [DEMO_RUN_DIR, "Maximum out-of-pocket change flag needs review: 2027 value read with confidence 0.6, below 0.7"],
    [TEXAS_RUN_DIR, "Drug deductible change flag needs review: not found in 2026; not found in 2027"],
  ])("retains the exact recorded reason and source data for %s", async (dir, label) => {
    const run = await loadRunDir(dir);
    const before = JSON.stringify(run);
    const original = run.reviewQueue.find(item => item.kind === "shop_again_uncertain")!.reason;
    render(<Trust run={run} />);
    const group = within(screen.getByRole("group", { name: "High: Change flag needs review" }));
    expect(group.getByText(label)).toBeVisible();
    expect(group.getByText(original)).not.toBeVisible();
    expect(group.getByText("Original recorded reason").closest("details")).not.toHaveAttribute("open");
    expect(JSON.stringify(run)).toBe(before);
  });

  it("leaves other explanations intact without an unnecessary disclosure", () => {
    render(<ReviewReason reason="premium up $25 a month" />);
    expect(screen.getByText("Premium up $25 a month")).toBeVisible();
    expect(screen.queryByText("Original recorded reason")).not.toBeInTheDocument();
  });
});
