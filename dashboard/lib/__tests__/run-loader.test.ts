import { cp, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { tmpdir } from "node:os";
import { describe, expect, it } from "vitest";

import { formatMoney } from "@/lib/money";
import { overviewRows, reviewFlagText, summary } from "@/lib/overview";
import { DEMO_RUN_DIR, loadRunDir } from "@/lib/run-dir";
import { parseRun, type RunFiles } from "@/lib/run-loader";

async function demoFiles(): Promise<RunFiles> {
  const read = (name: string) => readFile(path.join(DEMO_RUN_DIR, name), "utf8");
  const plans = ["H9999-001", "H9999-002", "H9999-003", "H9999-004"];
  return {
    manifest: await read("manifest.json"),
    accuracy: await read("accuracy.json"),
    reviewQueue: await read("review_queue.jsonl"),
    diffs: Object.fromEntries(await Promise.all(plans.map(async (p) => [p, await read(`diff/${p}.json`)]))),
  };
}

describe("formatMoney", () => {
  it.each([
    ["25.00", "$25.00"],
    ["1234567.50", "$1,234,567.50"],
    ["-24.50", "-$24.50"],
    ["0.00", "$0.00"],
  ])("formats %s as %s", (text, shown) => {
    expect(formatMoney(text)).toBe(shown);
  });

  it.each(["25.0.5", "1e3", "", "$5.00"])("refuses %j", (text) => {
    expect(() => formatMoney(text)).toThrow(/money/);
  });
});

describe("loadRunDir", () => {
  it.each(["diff", "plans", "diff/H9999-001.json", "plans/H9999-001_2026.json"])("refuses missing %s instead of presenting an incomplete run", async (missing) => {
    const dir = await mkdtemp(path.join(tmpdir(), "plan-diff-test-"));
    try {
      await cp(DEMO_RUN_DIR, dir, { recursive: true });
      await rm(path.join(dir, missing), { recursive: true });
      await expect(loadRunDir(dir)).rejects.toThrow(/diff|plan/);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("refuses a truncated review queue instead of understating unresolved work", async () => {
    const dir = await mkdtemp(path.join(tmpdir(), "plan-diff-test-"));
    try {
      await cp(DEMO_RUN_DIR, dir, { recursive: true });
      const queue = path.join(dir, "review_queue.jsonl");
      const lines = (await readFile(queue, "utf8")).trim().split("\n");
      await writeFile(queue, lines.slice(1).join("\n"));
      await expect(loadRunDir(dir)).rejects.toThrow(/review_items count differs/);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("loads the committed demo run with all four diffs and every review item", async () => {
    const run = await loadRunDir(DEMO_RUN_DIR);
    expect(run.manifest.run_id).toBe("demo");
    expect(run.diffs.map((d) => d.old_plan_id)).toEqual(["H9999-001", "H9999-002", "H9999-003", "H9999-004"]);
    expect(run.reviewQueue).toHaveLength(run.manifest.counts.review_items);
  });

  it("names the file it could not read", async () => {
    await expect(loadRunDir(path.join(DEMO_RUN_DIR, "no-such-run"))).rejects.toThrow(/manifest\.json/);
  });
});

describe("parseRun", () => {
  it("refuses money written as a number", async () => {
    const files = await demoFiles();
    const manifest = JSON.parse(files.manifest);
    manifest.jev.cost_usd = 0.5;
    expect(() => parseRun({ ...files, manifest: JSON.stringify(manifest) })).toThrow(/cost_usd must be text/);
    const diff = JSON.parse(files.diffs["H9999-001"]);
    diff.changes[0].new.value.amount = 25;
    expect(() => parseRun({ ...files, diffs: { ...files.diffs, "H9999-001": JSON.stringify(diff) } })).toThrow(
      /diff\/H9999-001\.json: amount must be text/,
    );
  });

  it("refuses a manifest without the config the run used", async () => {
    const files = await demoFiles();
    const manifest = JSON.parse(files.manifest);
    expect(parseRun(files).manifest.config.confidence_floor).toBe(0.7);
    manifest.config.confidence_floor = "0.7";
    expect(() => parseRun({ ...files, manifest: JSON.stringify(manifest) })).toThrow(/confidence_floor must be a number/);
    delete manifest.config;
    expect(() => parseRun({ ...files, manifest: JSON.stringify(manifest) })).toThrow(/manifest\.json: missing config/);
  });

  it("refuses an unknown shop again value and names the review queue line", async () => {
    const files = await demoFiles();
    const diff = JSON.parse(files.diffs["H9999-004"]);
    diff.shop_again = "maybe";
    expect(() => parseRun({ ...files, diffs: { ...files.diffs, "H9999-004": JSON.stringify(diff) } })).toThrow(
      /shop_again/,
    );
    const broken = files.reviewQueue.replace('"severity":"high"', '"severity":"urgent"');
    expect(() => parseRun({ ...files, reviewQueue: broken })).toThrow(/review_queue\.jsonl line 1/);
  });
});

describe("overview data", () => {
  it("puts flagged plans first and undecided after them, with review counts per plan", async () => {
    const rows = overviewRows(await loadRunDir(DEMO_RUN_DIR));
    expect(rows.map((r) => [r.planId, r.shopAgain, r.reviewCount])).toEqual([
      ["H9999-001", true, 5],
      ["H9999-002", true, 2],
      ["H9999-003", true, 0],
      ["H9999-004", null, 2],
    ]);
  });

  it("never reads undecided as no", () => {
    expect(reviewFlagText(null)).toBe("Undecided, needs review");
    expect(reviewFlagText(true)).toBe("Flagged for review");
    expect(reviewFlagText(false)).toBe("No change flag");
  });

  it("summarizes the run with a labeled match rate", async () => {
    expect(summary(await loadRunDir(DEMO_RUN_DIR))).toEqual({
      compared: 4,
      flagged: 3,
      undecided: 1,
      reviewItems: 10,
      matchRate: "97.6%",
      matchContext: "41 of 42 comparable values, on synthetic fixtures, as of 2026-10-05. Synthetic test fixtures; not production accuracy.",
    });
  });
});
