# plan-diff

Project 2 of the Agency Data Trust Series. Turns public carrier benefit documents (Medicare Advantage
Evidence of Coverage and Summary of Benefits, ACA Summary of Benefits and Coverage) into one canonical
plan schema with page citations, then diffs plan years. Public documents and CMS public use files only.

## Commands
- `npm run verify`            all checks: ruff, mypy, pytest, eslint, tsc, vitest, next build. Must pass before any commit.
- `cd engine && uv run plan-diff version`   print the engine version.
- `uv run --project engine plan-diff fetch --manifest sources/manifest.json --out data/raw [--only ID] [--pin]`   download sources (Alex approves the file list first; never in CI). See docs/sources.md.
- `cd engine && uv run pytest -q tests/unit/test_cli.py -k version`   run one test file or test.
- `cd dashboard && npm run dev`   local dashboard.

## Invariants (never break these)
- Public data only: carrier PDFs posted publicly and CMS public use files. No PHI, no real client data, no SSNs, ever.
- Every extracted field carries page provenance: source document, page number, and extraction method.
  A value without a citation is not a value.
- Deterministic extraction first. An LLM or Jev result never overrides a deterministic parse; disagreements go to review.
- JEV_MODE defaults to replay. LLM calls default off or replay. live and record spend money and need Alex's
  approval every time. CI is always replay.
- Never read .env or any .env.* file. Secrets live only in .env, which git ignores.
- Downloaded PDFs and CMS files go in data/raw/, which git ignores. Never commit them in bulk.
  Small test fixtures go in fixtures/ with a note on where they came from.
- No PDF library yet. Picking one is a SPEC decision because of licenses (PyMuPDF is AGPL, this repo is MIT).

## Gotchas
- Use uv, not pip. Use polars, not pandas.
- Node 24 (Node 20 is end of life). Dashboard is Next 16; its APIs differ from older Next.
  Read node_modules/next/dist/docs/ before writing dashboard code.
- `typecheck` runs `next typegen` first, because Next 16 generates some page types at build time.
- Docs and UI strings: plain language, no em dashes.
- The repo path contains a space ("Data intake"). Quote every absolute path in shell commands and scripts.

## Workflow
- One PR per session per worktree. Branch names pr-NN-short-name. Under 400 changed lines.
- Tests first from SPEC examples, then implementation, then `npm run verify`, then show the output.
- Add one changelog fragment per PR in changelog.d/ (see changelog.d/README.md). Do not edit CHANGELOG.md directly.
- Never push, open a PR, merge, create a GitHub repo, or link Vercel without Alex's explicit go-ahead.
- Record lasting decisions as ADRs in docs/adr/.
