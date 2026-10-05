import type { AccuracyTable, PlanDiff, ReviewItem, RunManifest } from "@/lib/types";

// Parses one run's files from text, so the server (demo run) and the browser (a run you load) share
// it. Pattern copied from agency-intake-kit lib/run-loader.ts (a54faee). Basic shape checks only: the
// engine's models are the real validator. These catch a wrong folder, a mixed-up run, or money as a number.
export interface Run {
  manifest: RunManifest;
  accuracy: AccuracyTable;
  diffs: PlanDiff[];
  reviewQueue: ReviewItem[];
}

export interface RunFiles {
  manifest: string;
  accuracy: string;
  reviewQueue: string;
  /** diff/<old plan id>.json text, keyed by the old plan id. */
  diffs: Record<string, string>;
}

export const FILE_NAMES = { manifest: "manifest.json", accuracy: "accuracy.json", reviewQueue: "review_queue.jsonl" };
const SEVERITIES = ["low", "medium", "high"];
const DATA_KINDS = ["synthetic", "public"];
const MONEY_KEYS = ["amount", "percent", "cost_usd"];

function check(ok: boolean, where: string, problem: string): void {
  if (!ok) throw new Error(`${where}: ${problem}`);
}

/** JSON.parse that names the file (and line) when the text is broken, so users know what to fix. */
export function parseJson(text: string, where: string): unknown {
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`${where}: not valid JSON (${(error as Error).message})`);
  }
}

function object(value: unknown, where: string, keys: string[]): Record<string, unknown> {
  check(typeof value === "object" && value !== null && !Array.isArray(value), where, "expected an object");
  const record = value as Record<string, unknown>;
  for (const key of keys) check(key in record, where, `missing ${key}`);
  return record;
}

/** Walks the whole value: any amount, percent, or cost must be decimal text, never a JSON number. */
function moneyIsText(value: unknown, where: string): void {
  if (Array.isArray(value)) return value.forEach((item) => moneyIsText(item, where));
  if (typeof value !== "object" || value === null) return;
  for (const [key, inner] of Object.entries(value)) {
    if (MONEY_KEYS.includes(key)) check(typeof inner === "string", where, `${key} must be text`);
    moneyIsText(inner, where);
  }
}

export function parseRun(files: RunFiles): Run {
  const manifest = object(parseJson(files.manifest, FILE_NAMES.manifest), FILE_NAMES.manifest, [
    "run_id", "data_kind", "plans", "years", "inputs", "jev", "llm", "counts",
  ]);
  check(DATA_KINDS.includes(manifest.data_kind as string), FILE_NAMES.manifest, "data_kind must be synthetic or public");
  moneyIsText(manifest, FILE_NAMES.manifest);

  const accuracy = object(parseJson(files.accuracy, FILE_NAMES.accuracy), FILE_NAMES.accuracy, ["rows"]);
  check(Array.isArray(accuracy.rows), FILE_NAMES.accuracy, "rows must be a list");
  check(
    accuracy.run_id == null || accuracy.run_id === manifest.run_id,
    FILE_NAMES.accuracy,
    "manifest and accuracy are not from the same run",
  );

  const diffs = Object.entries(files.diffs).map(([plan, text]) => {
    const where = `diff/${plan}.json`;
    const diff = object(parseJson(text, where), where, [
      "old_plan_id", "new_plan_id", "crosswalk_status", "changes", "shop_again", "reasons",
    ]);
    check([true, false, null].includes(diff.shop_again as boolean | null), where, "shop_again must be true, false, or null");
    check(Array.isArray(diff.reasons) && Array.isArray(diff.changes), where, "reasons and changes must be lists");
    moneyIsText(diff, where);
    return { evidence: [], review: [], ...diff } as unknown as PlanDiff;
  });

  const lines = files.reviewQueue.split("\n").filter((line) => line.trim() !== "");
  const reviewQueue = lines.map((line, index) => {
    const where = `${FILE_NAMES.reviewQueue} line ${index + 1}`;
    const item = object(parseJson(line, where), where, ["kind", "plan_id", "reason", "severity"]);
    check(SEVERITIES.includes(item.severity as string), where, "unknown severity");
    return item as unknown as ReviewItem;
  });

  return {
    manifest: manifest as unknown as RunManifest,
    accuracy: { plans: [], years: [], run_id: null, as_of: null, ...accuracy } as unknown as AccuracyTable,
    diffs: diffs.sort((a, b) => (a.old_plan_id ?? "").localeCompare(b.old_plan_id ?? "")),
    reviewQueue,
  };
}
