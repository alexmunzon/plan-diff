import { readFile } from "node:fs/promises";
import path from "node:path";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Changes } from "@/components/changes";
import { DirectionText } from "@/components/change-parts";
import { Overview } from "@/components/overview";
import { PlanPicker } from "@/components/plan-picker";
import { RunNav } from "@/components/run-nav";
import { ThemeToggle } from "@/components/theme-toggle";
import { DEMO_RUN_DIR, loadRunDir, TEXAS_RUN_DIR } from "@/lib/run-dir";

vi.mock("next/navigation", () => ({ usePathname: () => "/texas/changes" }));

describe("consulting visual contract", () => {
  it("keeps one shared light and dark palette, responsive shell, and keyboard focus treatment", async () => {
    const css = await readFile(path.join(process.cwd(), "app/globals.css"), "utf8");
    for (const token of ["#292524", "#f5f5f4", "#ff2727", "#af0505", "#57534e", "#d6d3d1", "#1c1917", "#fafaf9", "#c7c2bb", "#ffb3aa"]) {
      expect(css.toLowerCase()).toContain(token);
    }
    expect(css).toContain(":focus-visible");
    expect(css).toContain("prefers-reduced-motion");
    expect(css).toContain("1320px");
    expect(css).toContain("232px");
    expect(css).toContain("background: var(--primary); border-color: var(--primary); color: #ffffff");
    expect(css).not.toMatch(/--(?:navy|teal):/);
    const severity = await readFile(path.join(process.cwd(), "components/severity-badge.tsx"), "utf8");
    expect(severity).not.toMatch(/#ff2727|#af0505/i);
    const layout = await readFile(path.join(process.cwd(), "app/layout.tsx"), "utf8");
    expect(layout).toContain('href="#main-content"');
    expect(layout).toContain('id="main-content"');
  });

  it("protects 375/390px touch targets and readable evidence without hiding content", async () => {
    const css = await readFile(path.join(process.cwd(), "app/globals.css"), "utf8");
    const mobile = css.slice(css.indexOf("@media (max-width: 1023px)"));
    expect(mobile).toContain(".theme-toggle, .nav-item, .run-option, .action-link { min-height: 44px; }");
    expect(mobile).toContain(".sidebar-links a, .plan-id, .document-panel a, .evidence-table a");
    expect(mobile).toContain("font-size: 12px; line-height: 1.55;");
    expect(mobile).not.toMatch(/display:\s*none|overflow:\s*hidden|line-clamp/);
    expect(css).toMatch(/\.app-main \{[^}]*min-width: 0/);
    expect(mobile).toContain(".app-sidebar, .sidebar-support > * { min-width: 0; }");
  });

  it("keeps warm-neutral text and dark-red actions above AA contrast in both themes", () => {
    const luminance = (hex: string) => {
      const channels = [1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16) / 255);
      const linear = channels.map((v) => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
      return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
    };
    for (const [foreground, background] of [
      ["#292524", "#ffffff"], ["#57534e", "#ffffff"], ["#57534e", "#efeeeb"],
      ["#af0505", "#ffffff"], ["#292524", "#f5f5f4"], ["#fafaf9", "#292524"],
      ["#c7c2bb", "#292524"], ["#fafaf9", "#1c1917"], ["#c7c2bb", "#1c1917"],
      ["#c7c2bb", "#332e2a"], ["#ffb3aa", "#292524"], ["#fafaf9", "#433b37"],
      ["#ffffff", "#af0505"], ["#ffffff", "#850404"],
    ]) {
      const [dark, light] = [luminance(foreground), luminance(background)].sort((a, b) => a - b);
      expect((light + 0.05) / (dark + 0.05), `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it.each([[DEMO_RUN_DIR, "", "Synthetic demo"], [TEXAS_RUN_DIR, "/texas", "Public Texas run"]])("explains the run and offers a direct review action on %s", async (dir, base, label) => {
    render(<Overview run={await loadRunDir(dir)} base={base} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review evidence" })).toHaveAttribute("href", `${base}/trust#queue-heading`);
    expect(screen.getByRole("heading", { name: "Plans", level: 2 })).toBeVisible();
    expect(screen.getByRole("group", { name: "Accuracy match rate" })).toBeInTheDocument();
  });

  it("keeps the saved theme and pressed state in sync across repeated changes", async () => {
    document.documentElement.classList.remove("dark");
    localStorage.clear();
    render(<ThemeToggle />);
    const toggle = screen.getByRole("button", { name: "Dark mode" });
    fireEvent.click(toggle);
    await waitFor(() => expect(toggle).toHaveAttribute("aria-pressed", "true"));
    expect(localStorage.getItem("theme")).toBe("dark");
    fireEvent.click(toggle);
    await waitFor(() => expect(toggle).toHaveAttribute("aria-pressed", "false"));
    expect(localStorage.getItem("theme")).toBe("light");
  });

  it("keeps both Changes tables, every direction, and zero counts discoverable by keyboard", async () => {
    render(<Changes run={await loadRunDir(DEMO_RUN_DIR)} />);
    const counts = screen.getByRole("table", { name: "Fields by category and direction" });
    expect(screen.getByRole("table", { name: /Changes and values needing review/ })).toBeInTheDocument();
    expect(counts.closest("section")).toHaveAttribute("tabindex", "0");
    expect(counts).toHaveClass("min-w-[640px]");
    expect(screen.getByRole("table", { name: /Changes and values needing review/ })).toHaveClass("min-w-[720px]");
    expect(within(counts).getAllByText("0").length).toBeGreaterThan(10);
    for (const label of ["Up", "Down", "No change", "Added", "Removed", "Not comparable", "Needs review"]) {
      expect(within(counts).getByRole("columnheader", { name: label })).toHaveAttribute("scope", "col");
    }
  });

  it("gives movement directions the same neutral treatment", () => {
    render(<><DirectionText direction="up" /><DirectionText direction="down" /></>);
    expect(screen.getByText("Up")).toHaveClass("direction-label");
    expect(screen.getByText("Down")).toHaveClass("direction-label");
  });

  it("retains run-aware navigation and evidence download labels", () => {
    render(<RunNav />);
    expect(screen.getByRole("link", { name: "Changes" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Plan comparison" })).toHaveAttribute("href", "/texas/plans");
    expect(screen.getByRole("link", { name: "Review queue JSONL" })).toHaveAttribute("download");
  });

  it("makes plan selection a labeled list without changing destinations", async () => {
    render(<PlanPicker run={await loadRunDir(TEXAS_RUN_DIR)} base="/texas" />);
    expect(screen.getByRole("list", { name: "Available plans" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "H0028-030" })).toHaveAttribute("href", "/texas/plans/H0028-030");
  });
});
