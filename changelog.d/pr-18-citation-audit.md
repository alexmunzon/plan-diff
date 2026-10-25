## PR 18: Citation audit (2026-10-24)

- Add `plan-diff audit`: checks whether each declared benefit claim is supported by the page it cites, in the right plan, year, booklet pages, and version, and lists any other evidence that reads differently, including CMS mismatches the run already recorded.
- Add a versioned, immutable audit sidecar next to a run, never inside it, with a manifest of commit, input hashes, code and policy hashes, command, and timestamps. Reviewer corrections are new numbered files; the original verdict is never rewritten.
- Add a Citation audit page to the dashboard with a verdict filter, claim detail, contrary evidence, version context, unknowns, and downloads. Runs without an audit say so.
- Add 77 synthetic cases in three frozen sets with separately stored labels, a citation-exists-only baseline, and negative controls. Deterministic rules only; no model is called.
- Unknown effective dates now send a claim to a person (policy 2, Alex's decision); 13 dated cases and a frozen expectations file keep the original labels untouched.
- Fix twelve inputs two AI quality reviews showed were wrongly supported, plus their medium findings in scoring, adjudication, limits, provenance, and the dashboard.
- Require verified replacement context and declared date coverage before suppressing conflicting evidence. Preserve eight further exposed review cases and first-exposure failures.
- Correct the omitted d15 expectation in a separate frozen revision, validate serialized evaluation identity and verdicts, enforce override scope and rubric hashes, and isolate the scoring-forgery control.
- Bind claim amounts and not-covered statements to their named benefits, units, explicit plan/year and conditions; retain six additional exposed review cases and first failures.
- Refuse inconsistent supported dashboard artifacts while keeping intentionally weakened evaluation lanes visibly labeled. Disable automatic Vercel deployment for this review branch.
- Require recognized claim wording and clause-local conditions, units, payment kinds and network wording; check explicit as-of dates and preserve ten exposed post-build probes with their original failures.
- Bind exact audit bytes in completion manifest v2 and validate before display or adjudication. Preserve historical v1 artifacts; regenerate from original inputs for current use.
