import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { citationText, valueText } from "@/lib/compare";
import { summary } from "@/lib/overview";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";
import { parseRun } from "@/lib/run-loader";
import type { ExtractedField } from "@/lib/types";

const field = (value: ExtractedField["value"], unit: string | null): ExtractedField => ({
  name: "x", value, unit, confidence: 0.9, citation: { document_id: "D", page: 3, method: "rule" },
});

async function sources(dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true, recursive: true });
  return entries
    .filter((e) => e.isFile() && /\.tsx?$/.test(e.name) && !e.parentPath.includes("node_modules") && !e.parentPath.includes(".next"))
    .map((e) => path.join(e.parentPath, e.name));
}

describe("money and values", () => {
  it("formats money from text and keeps every digit a float would lose", () => {
    expect(valueText(field({ kind: "money", amount: "12345678901234567.89" }, "per_year"))).toBe(
      "$12,345,678,901,234,567.89 a year",
    );
    expect(valueText(field({ kind: "copay", amount: "45.00" }, "per_visit"))).toBe("$45.00 copay a visit");
    expect(valueText(field({ kind: "coinsurance", percent: "20" }, "per_day"))).toBe("20% coinsurance a day");
    expect(valueText(field({ kind: "not_covered" }, null))).toBe("Not covered");
    expect(valueText(null)).toBe("Not found in the document");
  });

  it("never parses money with parseFloat anywhere in the dashboard", async () => {
    const root = path.resolve(import.meta.dirname, "..", "..");
    const files = [...(await sources(path.join(root, "lib"))), ...(await sources(path.join(root, "components"))), ...(await sources(path.join(root, "app")))];
    expect(files.length).toBeGreaterThan(10);
    const self = path.join(root, "lib", "__tests__", "compare.test.ts");
    for (const file of files.filter((f) => f !== self)) expect(await readFile(file, "utf8"), file).not.toMatch(/parseFloat/);
  });

  it("writes citations as document and page, or CMS file and row", () => {
    expect(citationText({ document_id: "H9999-001_2026_SB", page: 2, method: "rule" })).toBe("H9999-001_2026_SB, page 2");
    expect(citationText({ document_id: "pbp_mrx.txt", page: 4, method: "cms" })).toBe("CMS file pbp_mrx.txt, row 4");
  });
});

describe("data kind", () => {
  it("comes from the manifest, not from the plan ids", async () => {
    const run = await loadRunDir(DEMO_RUN_DIR);
    expect(run.manifest.data_kind).toBe("synthetic");
    run.manifest.data_kind = "public"; // still H9999 plan ids
    expect(summary(run).matchContext).toBe("41 of 42 comparable values, across 4 public plans, as of 2026-10-05. Extraction rules were tuned on these same documents, not held-out measured accuracy. 6 values not comparable and 0 values not extracted.");
  });

  it("refuses a manifest without a valid data kind", async () => {
    const read = (name: string) => readFile(path.join(DEMO_RUN_DIR, name), "utf8");
    const files = { accuracy: await read("accuracy.json"), reviewQueue: await read("review_queue.jsonl"), diffs: {} };
    const manifest = JSON.parse(await read("manifest.json"));
    delete manifest.data_kind;
    expect(() => parseRun({ ...files, manifest: JSON.stringify(manifest) })).toThrow(/missing data_kind/);
    manifest.data_kind = "real";
    expect(() => parseRun({ ...files, manifest: JSON.stringify(manifest) })).toThrow(/synthetic or public/);
  });
});
