import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { render, screen, within } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import RootLayout from "@/app/layout";
import { Changes } from "@/components/changes";
import { DirectionText } from "@/components/change-parts";
import { Overview } from "@/components/overview";
import { PlanPicker } from "@/components/plan-picker";
import { RunNav } from "@/components/run-nav";
import { DEMO_RUN_DIR, loadRunDir, TEXAS_RUN_DIR } from "@/lib/run-dir";

vi.mock("next/navigation", () => ({ usePathname: () => "/texas/changes" }));

describe("consulting visual contract", () => {
  it("keeps one shared light palette, responsive shell, and keyboard focus treatment", async () => {
    const css = await readFile(path.join(process.cwd(), "app/globals.css"), "utf8");
    for (const token of ["#272727", "#f6f5f2", "#ffffff", "#8f202b", "#646464", "#858585", "#b4233b", "#805600", "#246442"]) {
      expect(css.toLowerCase()).toContain(token);
    }
    expect(css).toContain(":focus-visible");
    expect(css).toContain("prefers-reduced-motion");
    expect(css).toContain("1320px");
    expect(css).toContain("232px");
    expect(css).toContain("background: var(--primary); border-color: var(--border); color: #ffffff");
    expect(css).not.toMatch(/--(?:navy|teal):/);
    const severity = await readFile(path.join(process.cwd(), "components/severity-badge.tsx"), "utf8");
    expect(severity).not.toMatch(/#8f202b/i);
    const layout = await readFile(path.join(process.cwd(), "app/layout.tsx"), "utf8");
    expect(layout).toContain('href="#main-content"');
    expect(layout).toContain('id="main-content"');
  });

  it("protects 375/390px touch targets and readable evidence without hiding content", async () => {
    const css = await readFile(path.join(process.cwd(), "app/globals.css"), "utf8");
    const mobile = css.slice(css.indexOf("@media (max-width: 1023px)"));
    expect(mobile).toContain(".nav-item, .run-option, .action-link { min-height: 44px; }");
    expect(mobile).toContain(".sidebar-links a, .plan-id, .document-panel a, .evidence-table a");
    expect(mobile).toContain("font-size: 12px; line-height: 1.55;");
    expect(mobile).not.toMatch(/display:\s*none|overflow:\s*hidden|line-clamp/);
    expect(css).toMatch(/\.app-main \{[^}]*min-width: 0/);
    expect(mobile).toContain(".app-sidebar, .sidebar-support > * { min-width: 0; }");
  });

  it("keeps actual light palette text, status and action colors above AA contrast", async () => {
    const luminance = (hex: string) => {
      const channels = [1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16) / 255);
      const linear = channels.map((v) => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
      return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
    };
    const css = await readFile(path.join(process.cwd(), "app/globals.css"), "utf8");
    const tokens = (selector: string) => Object.fromEntries(
      [...css.match(new RegExp(`${selector} [{]([^}]+)`))![1].matchAll(/--([\w-]+): ([^;]+);/g)]
        .map((match) => [match[1], match[2]]),
    );
    for (const theme of [tokens(":root")]) {
      const color = (name: string): string => {
        const value = theme[name];
        return value.startsWith("var(") ? color(value.slice(6, -1)) : value;
      };
      const contrast = (a: string, b: string) => {
        const [dark, light] = [luminance(a), luminance(b)].sort((x, y) => x - y);
        return (light + 0.05) / (dark + 0.05);
      };
      for (const background of ["paper", "panel"]) {
        for (const foreground of ["ink", "muted", "status-error", "status-warning", "status-pass"]) {
          expect(contrast(color(foreground), color(background)), `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5);
        }
        expect(contrast(color("border"), color(background)), `control border on ${background}`).toBeGreaterThanOrEqual(3);
      }
      expect(contrast(color("selected-ink"), color("primary"))).toBeGreaterThanOrEqual(4.5);
    }
  });

  it.each([[DEMO_RUN_DIR, "", "Synthetic demo"], [TEXAS_RUN_DIR, "/texas", "Public Texas run"]])("explains the run and offers a direct review action on %s", async (dir, base, label) => {
    render(<Overview run={await loadRunDir(dir)} base={base} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review evidence" })).toHaveAttribute("href", `${base}/trust#queue-heading`);
    expect(screen.getByRole("heading", { name: "Plans", level: 2 })).toBeVisible();
    expect(screen.getByRole("group", { name: "Accuracy match rate" })).toBeInTheDocument();
  });

  it("always renders the light palette with no dark mode toggle, script or styles", async () => {
    const css = await readFile(path.join(process.cwd(), "app/globals.css"), "utf8");
    expect(css).not.toMatch(/\.dark\b/);
    expect(css).not.toMatch(/prefers-color-scheme/);
    expect(css).not.toMatch(/@custom-variant\s+dark/);
    expect(css).not.toMatch(/\.theme-toggle/);
    expect(css).toMatch(/:root \{[^}]*color-scheme: light;/);
    const layout = await readFile(path.join(process.cwd(), "app/layout.tsx"), "utf8");
    expect(layout).not.toMatch(/prefers-color-scheme|localStorage|matchMedia|data-theme|ThemeToggle|theme-toggle/);
    expect(layout).not.toMatch(/classList|["'\s]dark["'\s]/);
    await expect(readFile(path.join(process.cwd(), "components/theme-toggle.tsx"), "utf8")).rejects.toThrow();
    const sources = (await readdir(process.cwd(), { recursive: true }))
      .filter((file) => /\.(tsx?|css)$/.test(file) && !/^(node_modules|\.next|vendor)\//.test(file) && !file.includes("__tests__"));
    expect(sources.length).toBeGreaterThan(10);
    for (const file of sources) {
      const source = await readFile(path.join(process.cwd(), file), "utf8");
      expect(source, file).not.toMatch(/(?<![\w-])dark:/);
      expect(source, file).not.toMatch(/Dark mode/i);
    }
  });

  it("ignores a stale stored dark preference and renders a shell with no dark mode control or theme script", () => {
    localStorage.setItem("theme", "dark");
    try {
      const html = renderToStaticMarkup(<RootLayout params={Promise.resolve({})}><p>page</p></RootLayout>);
      expect(html).toMatch(/^<html[^>]*class="h-full antialiased"/);
      expect(html).not.toMatch(/<html[^>]*class="[^"]*\bdark\b/);
      expect(html).not.toMatch(/<script/);
      expect(html).not.toMatch(/dark mode/i);
      expect(html).not.toMatch(/aria-pressed/);
      expect(html).toContain("plan-diff");
      expect(document.documentElement).not.toHaveClass("dark");
    } finally {
      localStorage.clear();
    }
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
