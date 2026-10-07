## PR 20: Remove braces entirely (2026-10-06)

- Give Next's lint plugin a small local fast-glob stand-in built on Node's `fs.globSync` (npm override,
  copied from agency-intake-kit), so braces GHSA-vfj7-8cjw-p6xm (no patched release) and micromatch are
  no longer installed. 15 packages removed, none upgraded; full `npm audit` now reports zero findings.
- The stand-in matches fast-glob 3.3.1 on recorded ordinary `rootDir` patterns and refuses brace
  patterns; a new test checks the lockfile, the resolution and the patterns. All lint rules still run.
  The deployed site is unchanged.
