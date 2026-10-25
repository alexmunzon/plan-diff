import { fireEvent, render, screen, within } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { CitationAudit, NoAudit } from "@/components/citation-audit";
import { RunNav } from "@/components/run-nav";
import { loadAudit } from "@/lib/audit-dir";
import { DEMO } from "@/lib/runs";

const path = vi.hoisted(() => ({ current: "/audit" }));
vi.mock("next/navigation", () => ({ usePathname: () => path.current }));

async function demo() {
  const audit = await loadAudit(DEMO);
  if (!audit) throw new Error("the demo audit is missing: run `npm run audit-demo`");
  return audit;
}

const claim = (text: RegExp) => screen.getByRole("button", { name: text });

describe("Citation audit page", () => {
  it("labels the audit as synthetic, offline, and model not run", async () => {
    render(<CitationAudit audit={await demo()} runLabel={DEMO.label} folder="demo-run-audit" />);
    expect(screen.getByRole("heading", { level: 1, name: "Does the cited evidence support each claim?" })).toBeInTheDocument();
    expect(screen.getByText("Synthetic demo")).toBeInTheDocument();
    expect(screen.getByText("Model lane: not run")).toBeInTheDocument();
    expect(within(screen.getByLabelText("About this audit")).getByText("No model was called. No person has adjudicated these claims.")).toBeInTheDocument();
  });

  it("filters claims by verdict with keyboard-reachable buttons", async () => {
    render(<CitationAudit audit={await demo()} runLabel={DEMO.label} folder="demo-run-audit" />);
    const list = () => within(screen.getByRole("list", { name: "Claims" })).getAllByRole("listitem");
    expect(list()).toHaveLength(8);
    const filter = screen.getByRole("button", { name: "Needs a person (2)" });
    expect(filter.tagName).toBe("BUTTON");
    fireEvent.click(filter);
    expect(filter).toHaveAttribute("aria-pressed", "true");
    expect(list()).toHaveLength(2);
    expect(screen.getByRole("heading", { level: 2, name: "demo-04-platinum-moop" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Source cannot be checked (0)" })).toBeDisabled();
  });

  it("shows why an existing citation to a real page still fails: wrong plan year", async () => {
    render(<CitationAudit audit={await demo()} runLabel={DEMO.label} folder="demo-run-audit" />);
    fireEvent.click(claim(/premium is \$25 per month in 2026/));
    const detail = screen.getByRole("region", { name: "demo-02-premium-wrong-year" });
    expect(within(detail).getAllByText("Wrong plan, year, or version", { selector: ".severity-badge" }).length).toBeGreaterThan(0);
    const source = within(detail).getByRole("group", { name: "Source 1" });
    // The quote given and the row read are the same words here, so both are shown.
    expect(within(source).getAllByText("Monthly plan premium $25 per month", { selector: "q" })).toHaveLength(2);
    const year = within(source).getByRole("row", { name: "Document is for this plan and year" });
    expect(within(year).getByText("Fail")).toBeInTheDocument();
    expect(within(year).getByText("document is H9999-001 2027; claim is H9999-001 2026")).toBeInTheDocument();
    expect(within(source).getByText(/Effective 2027-01-01 to 2027-12-31/)).toBeInTheDocument();
  });

  it("shows the contrary CMS row next to a supporting citation", async () => {
    render(<CitationAudit audit={await demo()} runLabel={DEMO.label} folder="demo-run-audit" />);
    fireEvent.click(claim(/specialist visit costs \$45/));
    const contrary = within(screen.getByRole("group", { name: "Contrary evidence" }));
    expect(contrary.getByText(/CMS file .*row \d+: the run recorded a CMS mismatch/)).toBeInTheDocument();
    expect(screen.getAllByText("Conflicting evidence", { selector: ".severity-badge" }).length).toBeGreaterThan(0);
  });

  it("surfaces each part of a compound claim", async () => {
    render(<CitationAudit audit={await demo()} runLabel={DEMO.label} folder="demo-run-audit" />);
    fireEvent.click(claim(/Tier 2 generic drugs are \$5/));
    const premium = within(screen.getByRole("region", { name: "Part monthly_premium" }));
    const tier = within(screen.getByRole("region", { name: "Part drug_tier_2" }));
    expect(premium.getAllByText("Supported", { selector: ".severity-badge" }).length).toBeGreaterThan(0);
    expect(tier.getAllByText("Contradicted", { selector: ".severity-badge" }).length).toBeGreaterThan(0);
  });

  it("offers the audit files for download and escapes claim text", async () => {
    const audit = await demo();
    render(<CitationAudit audit={audit} runLabel={DEMO.label} folder="demo-run-audit" />);
    expect(screen.getByRole("link", { name: "Audit JSON" })).toHaveAttribute("href", "/demo-run-audit/audit.json");
    expect(screen.getByRole("link", { name: "Audit manifest JSON" })).toHaveAttribute("download");
    audit.sidecar.claims[0].claim.text = "<img src=x onerror=alert(1)>";
    const html = renderToStaticMarkup(<CitationAudit audit={audit} runLabel={DEMO.label} folder="demo-run-audit" />);
    expect(html).toContain("&lt;img src=x onerror=alert(1)&gt;");
    expect(html).not.toContain("<img");
  });

  it("warns, and only then, when the audit ran with safeguards switched off", async () => {
    const audit = await demo();
    render(<CitationAudit audit={audit} runLabel={DEMO.label} folder="demo-run-audit" />);
    expect(screen.queryByRole("alert")).toBeNull();
    audit.sidecar.policy.check_contrary = false;
    render(<CitationAudit audit={audit} runLabel={DEMO.label} folder="demo-run-audit" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Safeguards were switched off for this audit: the search for contrary evidence.");
  });

  it("says plainly when a run has no audit", () => {
    render(<NoAudit runLabel="Texas 2026 to 2027 (public)" />);
    expect(screen.getByRole("heading", { level: 2, name: "No citation audit has been run for Texas 2026 to 2027 (public)." })).toBeInTheDocument();
  });

  it("links the audit from the run navigation, following the run you are in", () => {
    path.current = "/texas/audit";
    render(<RunNav />);
    expect(screen.getByRole("link", { name: "Citation audit" })).toHaveAttribute("href", "/texas/audit");
    expect(screen.getByRole("link", { name: "Citation audit" })).toHaveAttribute("aria-current", "page");
  });
});
