import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

import { FILE_NAMES, parseRun, type Run, type RunFiles } from "@/lib/run-loader";

// Server only: reads a run folder from disk. Pages call this at build time for the committed demo
// run. The parsing lives in run-loader, so a run loaded in the browser is checked the same way.
export const DEMO_RUN_DIR = path.join(process.cwd(), "public", "demo-run");

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
  return parseRun({
    manifest,
    accuracy: await read(dir, FILE_NAMES.accuracy),
    reviewQueue: await read(dir, FILE_NAMES.reviewQueue),
    diffs,
  });
}
