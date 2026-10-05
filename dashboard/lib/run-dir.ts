import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

import { FILE_NAMES, parseRun, type Run, type RunFiles } from "@/lib/run-loader";
import { DEMO, TEXAS, type RunChoice } from "@/lib/runs";

// Server only: reads a run folder from disk. Pages call this at build time for the committed runs.
// The parsing lives in run-loader, so a run loaded in the browser is checked the same way.
export const runDir = (run: RunChoice) => path.join(process.cwd(), "public", run.folder);
export const DEMO_RUN_DIR = runDir(DEMO);
export const TEXAS_RUN_DIR = runDir(TEXAS); // PR 15: the real Texas slice

async function read(dir: string, name: string): Promise<string> {
  try {
    return await readFile(path.join(dir, name), "utf8");
  } catch {
    throw new Error(`Could not read ${name} in ${dir}`);
  }
}

export async function loadRunDir(dir: string): Promise<Run> {
  const manifest = await read(dir, FILE_NAMES.manifest);
  const names = (await readdir(path.join(dir, "diff")).catch(() => [])).filter((name) => name.endsWith(".json"));
  const diffs: RunFiles["diffs"] = {};
  for (const name of names) diffs[name.slice(0, -".json".length)] = await read(dir, `diff/${name}`);
  const planNames = (await readdir(path.join(dir, "plans")).catch(() => [])).filter((name) => name.endsWith(".json"));
  const plans: Record<string, string> = {};
  for (const name of planNames.sort()) plans[name.slice(0, -".json".length)] = await read(dir, `plans/${name}`);
  return parseRun({
    manifest,
    accuracy: await read(dir, FILE_NAMES.accuracy),
    reviewQueue: await read(dir, FILE_NAMES.reviewQueue),
    diffs,
    validation: await read(dir, FILE_NAMES.validation),
    plans,
  });
}
