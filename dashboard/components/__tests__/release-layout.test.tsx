import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import RootLayout from "@/app/layout";

vi.mock("next/navigation", () => ({ usePathname: () => "/texas/changes" }));

describe("Release navigation", () => {
  it("keeps plan evidence navigation in the selected run and links delivered pages", () => {
    const html = renderToStaticMarkup(<RootLayout params={Promise.resolve({})}>page</RootLayout>);
    const doc = new DOMParser().parseFromString(html, "text/html");
    const links = [...doc.querySelectorAll('ul[aria-label="Pages"] a')];
    expect(links).toHaveLength(5);
    for (const link of links) {
      const href = link.getAttribute("href")!;
      expect(href).toMatch(/^\/texas(?:\/|$)/);
      expect(existsSync(resolve(import.meta.dirname, `../../app${href}/page.tsx`))).toBe(true);
    }
    expect(doc.querySelector('ul[aria-label="Pages"] a[aria-current="page"]')?.getAttribute("href")).toBe("/texas/changes");
    expect(doc.querySelector('a[href="#main-content"]')).not.toBeNull();
    expect(doc.querySelector("main")?.getAttribute("tabindex")).toBe("-1");
  });

  it("separates plan change signals from enrollment and authenticated approval", () => {
    const html = renderToStaticMarkup(<RootLayout params={Promise.resolve({})}>page</RootLayout>);
    const doc = new DOMParser().parseFromString(html, "text/html");
    const scope = doc.querySelector('[aria-label="Review scope"]');
    expect(scope?.textContent).toContain("Human review required");
    expect(scope?.textContent).not.toContain("Synthetic");
    expect(scope?.textContent).toContain("Plan changes are review signals");
    expect(scope?.textContent).toContain("separately supplied enrollment evidence");
    expect(scope?.textContent).toContain("Browser review labels are not authenticated approval");
  });
});
