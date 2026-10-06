# plan-diff

Which Medicare Advantage plans changed enough that a client should shop again? plan-diff reads
public carrier benefit documents, keeps a document-and-page citation on every extracted value,
checks against CMS public data, and compares plan years using the CMS crosswalk.

[Open the demo](https://plan-diff.vercel.app) · [Public Texas run](https://plan-diff.vercel.app/texas)

For an asynchronous review, follow the five-minute walkthrough below, then inspect the downloaded
run evidence. For development, start with [locked setup](#run-locally), the
[documentation index](docs/README.md), [contributing](CONTRIBUTING.md), and [security](SECURITY.md).

## Status and scope

The dashboard has Overview, Plan comparison, Changes, Trust, and Documents for two committed runs:

- **Synthetic**, at `/`: four made-up plans, generated PDFs, and CMS-shaped fixtures. Shows known
  changes, a consolidation, a termination, a PDF/CMS disagreement, and an undecided result.
- **Public Texas**, at `/texas`: H0028-030 and H5294-014, 2026 versus 2027, recorded on 2026-10-05.
  Outputs come from 12 public carrier documents and CMS files. Source PDFs are not included.

This is a read-only recruiting demo. It has no client records, enrollment workflow, or live refresh.
The dashboard reads committed outputs at build time. Jev and LLM calls are off in both runs.
Shop again is a broker review flag, not suitability or coverage advice or an automatic client worklist.

## Five-minute walkthrough

1. Start at [Overview](https://plan-diff.vercel.app). H9999-001 is flagged because its premium rose
   $25 a month; H9999-002 consolidated into H9999-001; H9999-003 terminated according to CMS.
   H9999-004 is **undecided**, because its next-year maximum out-of-pocket value is ambiguous.
2. Open [H9999-001](https://plan-diff.vercel.app/plans/H9999-001). Compare all 15 fields, with
   values, units, page citations, and change directions. Missing values stay missing; a cited $0
   remains $0. Low-confidence or disputed values show their source text and need review, even
   when the extracted amounts look unchanged.
3. Open [Trust](https://plan-diff.vercel.app/trust). The synthetic specialist copay is $45 in the
   PDF and $40 in CMS. Both sources are shown, the disagreement goes to review, and neither wins.
4. Switch to [Public Texas](https://plan-diff.vercel.app/texas). Humana H0028-030 is flagged for a
   drug deductible increase of $85. Wellcare H5294-014 is flagged for losing 33 service-area
   counties. The comparison page includes the CMS crosswalk evidence.
5. Open [Texas Trust](https://plan-diff.vercel.app/texas/trust), then
   [Documents](https://plan-diff.vercel.app/texas/documents). Inspect the review queue and follow
   a carrier citation to its original HTTPS PDF page. Synthetic documents have no external PDF.
   The navigation also downloads the selected run's manifest, accuracy JSON, and review JSONL.

The Changes page groups changes by benefit category. Switching runs keeps the page navigation
inside that run. Unknown plan URLs show a recovery page. Missing plan/diff files and mismatched
plan/diff/review counts fail verification instead of silently reducing the results.

## What the numbers mean

- Synthetic fixtures: **41 of 42 comparable values match**, with 6 not comparable and 42 not in CMS.
- Public Texas: **48 of 48 comparable values match**, with 2 not comparable and 10 not extracted.
  These rules were tuned on those same documents. This is an in-sample check, not held-out accuracy.
- Every Trust page labels the slice, run ID, date, denominator, and separate excluded counts.
  These figures do not establish accuracy on new carrier documents.
- Wellcare's missing drug fields are not zero-dollar coverage. Its shared OTC card figure does
  not establish an OTC-only balance. Ambiguous grid values and unsupported periods need review.

Shop-again rules include a $20 monthly premium increase, $1,000 maximum out-of-pocket increase,
any drug-deductible increase, explicit removal of a benefit, termination/consolidation, or lost
counties. The run manifest records thresholds. Missing data never proves termination or removal;
uncertainty stays visible even when another supported reason already flags the plan.

## Run locally

You need Node 24 and [uv](https://docs.astral.sh/uv/), which manages Python 3.12.

```sh
cd engine && uv sync --locked && cd ..
cd dashboard && npm ci && cd ..
npm run verify                # ruff, mypy, pytest, eslint, typecheck, vitest, production build
npm run demo                  # regenerate only the deterministic synthetic JSON outputs
cd dashboard && npm run dev   # http://localhost:3000 and /texas
```

Both committed runs work without source downloads, credentials, or paid model calls. Tests do
not use the network. `npm run demo` leaves the public Texas run untouched.
Dependency installation requires registry access. Do not use `npm install` or an unlocked sync
for the canonical quickstart. The root package only coordinates scripts and has no dependencies
or lockfile; dashboard packages are locked in `dashboard/package-lock.json`, and Python packages
in `engine/uv.lock`.

## Architecture and repository map

The Python CLI classifies public PDFs, extracts cited fields, validates against CMS, and compares
years using the crosswalk. It writes a manifest plus plan, validation, diff, accuracy, and review
outputs. The Next.js dashboard renders two committed JSON snapshots at build time. It does not
run the parser, fetch carrier files, or call a model when a visitor opens a page.

- `engine/src/plan_diff/`: CLI and schema models; `classify/`, `extract/`, `cms/`, `validate/`,
  `diff/`, and `run/` separate the processing stages
- `engine/tests/` and `fixtures/`: offline parser, validation, safety, and deterministic-run checks
- `dashboard/app/` and `dashboard/components/`: routes and presentation, including `/texas`
- `dashboard/lib/`: run loading, consistency checks, exact-money display, and comparisons
- `dashboard/public/{demo-run,texas-run}/`: intentionally public, committed evidence snapshots
- `sources/manifest.json`: source URLs, pinned hashes, and retrieval metadata
- `data/raw/` and `runs/`: git-ignored local inputs and generated runs
- `docs/`: schema, CMS mappings, source policy, methods, and historical implementation notes

Run JSON is a build input, not an authenticated upload format. TypeScript checks basic shape,
decimal text, and manifest counts; Python models define the canonical schema. Page citations and
hashes establish traceability and byte identity, not correctness or fitness for a client decision.

## Evidence and safeguards

`dashboard/public/{demo-run,texas-run}/` contains `manifest.json`, `accuracy.json`,
`validation.json`, `review_queue.jsonl`, `plans/*.json`, and `diff/*.json`. Money is decimal text.
Public page links come from hash-pinned source URLs; this site never serves or proxies carrier PDFs.
Carrier availability and PDF page navigation depend on the carrier and browser.

New downloads require approval of the exact file list and use the hash-checking fetch command.
Raw files stay in git-ignored `data/raw/`. No PHI, private client data, or bulk PDFs belong here.
Deterministic extraction takes precedence; disagreements and missing evidence stay in review.

See the [documentation index](docs/README.md), [SPEC](SPEC.md), [schema](docs/schema.md), [sources](docs/sources.md), and
[public-run methods and limitations](docs/pr-15-notes.md). Optional Jev/LLM fallbacks, held-out
validation on new layouts, ACA support, and broader production workflows remain future work.

The 2026-10-06 dependency review found no production npm advisories, but the development toolchain
retains the unpatched `braces` advisory GHSA-vfj7-8cjw-p6xm. See [SECURITY.md](SECURITY.md) for the
bounded checks, trust boundaries, and remaining work. This demo is not a production security review.

## Agency Data Trust Series

Separate demos, shared trust principles. No data is transferred between these apps.

1. [Intake Kit](https://agency-intake-kit.vercel.app): inspect carrier intake and validation
2. [Bob Resolve](https://bob-resolve-nine.vercel.app): inspect record matching and review
3. [Plan Diff](https://plan-diff.vercel.app): inspect benefit changes and source evidence
