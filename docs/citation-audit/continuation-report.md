# Citation audit continuation: results and reflection

This is the preserved build baseline at commit `40baca7`. The separately requested
[deferred deeper pass](deep-improvement-plan.md) starts from that baseline and retains its evidence.

The existing build was continued from migration handoffs on `pr-18-citation-audit`.
Original conversation histories were not transferred. Local implementation and verification
are complete within the synthetic, deterministic scope below. This is not a real-carrier,
human-calibrated or general semantic validation claim.

## Repairs and retained evidence

Replacement documents must be readable, have declared date coverage and apply to the same
plan/year/booklet before they may suppress contrary evidence. Cyclic authority edges dismiss
nothing. Unknown effective dates remain a separate human-review outcome under policy 2.

Claim wording now binds each amount to its named benefit and own unit, including equal-amount
compound claims. Explicit plan/year text must agree with typed context; typed conditions must
appear in the text. The not-covered path also checks benefit identity. These are conservative
grammar checks, not a comprehensive interpretation of arbitrary prose.

The dashboard rejects supported artifacts with failed/missing wording checks, unknown dates
under policy 2, missing required source checks, missing/unreadable document evidence, or live
contrary evidence. Deliberately weakened evaluation lanes remain inspectable and visibly labeled.

Evaluation now validates serialized reports without depending on JSON key order, rejects
invalid verdicts and forged schema/lane/policy/input identity, enforces override scope and
rubric byte identities, and isolates the scoring-forgery control. The d15 expectation omission
is corrected by a separately frozen revision. Hash consistency does not prove freeze chronology.

All 32 original fixture/evidence files match the migration snapshot. The original 77 exposed
cases retain their labels and histories. New sets v5-v9 and first failures are append-only.
Review-15 preserves five false supports before decomposition repairs; review-16 preserves
eight dashboard integrity failures; review-18 preserves the not-covered false support.
All are exposed regressions, not untouched holdout or independent human labels.

## Verification

The final full command from the repository root exited 0:

```sh
UV_CACHE_DIR=/tmp/plan-diff-uv-cache UV_NO_SYNC=1 RUFF_NO_CACHE=true \
MYPY_CACHE_DIR=/tmp/plan-diff-mypy-cache PYTHONDONTWRITEBYTECODE=1 \
PYTEST_ADDOPTS='-p no:cacheprovider' PYTHONPATH=engine/src:engine/tests npm run verify
```

Passed Ruff lint/format (81 files), mypy (43 source files), **662 engine tests, 1 skipped**,
ESLint, Next route generation/TypeScript, **167 dashboard tests in 18 files**, and the production
build (21 generated pages). No dependencies were added. Verification scripts and gates were
not relaxed. The earlier Next generated-file EPERM was resolved through explicit user approval
and supported permission escalation at the existing path; no cache deletion or output redirection.

[eval-19](evidence/eval-19-after-final-review-fixes.json) records **106/106 agreement**,
**0 false supports among 101 negatives**, **5/5 supported positives**, **66/106 abstentions**,
and **9/9 controls caught**. The citation-exists baseline falsely supports **93/101** negatives.
The legacy lane remains **77/77**. These constructed, exposed samples do not establish real-world
accuracy. The honest not-covered positive is additionally checked in the unit suite.

Reproduction from `engine/`:

```sh
UV_CACHE_DIR=/tmp/plan-diff-uv-cache UV_NO_SYNC=1 PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src:tests uv run python tests/citation_audit_eval.py --out /tmp/new-audit-eval.json
```

Use a new output filename. Prior evidence files are never overwritten.
The demo was rebuilt through `audit_demo.build()`; audit.json remained byte-identical.
Its manifest now binds audit code hash
`718d50d83e643ddf0ed0a49247aa08acbedf1d6b3236438237221f16a7fd7130`.

## Browser and artifact validation

The final production build ran on loopback. A hidden in-app browser checked the real routes
without taking Chrome focus: supported detail and exact quote/page/hash, conflict filtering
with recorded CMS contrary evidence, keyboard activation, partial compound contradiction,
human-review cases, public-run navigation, and the explicit no-audit state on `/texas/audit`.
At 390 x 844 the document width was 390 pixels with no horizontal page overflow; filters and
claims remained readable. Captured browser error/warning logs were empty.

Both JSON download URLs returned HTTP 200 with application/json and bytes matching the
recorded artifacts. Browser download-event confirmation timed out through both supported
download methods, so OS-level download completion is not claimed. Link markup and served
payloads were checked; this is a browser automation limitation retained in the receipt.

## Independent review and reflection

Two prior Astra reviews were collected before edits. Continuation reviewers then found and
reproduced replacement-context, evaluation, wording and dashboard-integrity defects.
The final targeted checks closed the reported findings, including the not-covered counterexample
and its honest positive. A loader integration review accepted all 735 existing envelopes
(105 cases across seven policies) while rejecting all eight inconsistent default-policy artifacts.
The later v9 case is covered by the final suite/evaluation. These are bounded repair reviews,
not two clean whole-product reviews or human validation.

Green regression results repeatedly hid new false-support paths. The report therefore makes
no healthcare correctness guarantee and no untouched-holdout claim. Five supported positives
and 62% abstention provide weak usefulness evidence. Free-form wording, unsupported benefit
aliases, geography/tier semantics, real carrier layouts and unsearchable unreadable sources
still need human assessment. The newest adjudication revision remains unanchored by a later one.

The implementation reuses extraction and context logic, with small claim-wording aliases.
No model adapter, workflow framework, retrieval stack or dependency was added. Existing fault
tests cover malformed/missing/corrupt artifacts, limits, immutable output and adjudication chains.
[bench-05](evidence/bench-05-final.json) measured 8/100/500 claims at 0.502/1.018/1.917 seconds,
seven PDF reads each, 14 pages and 20,661 source bytes. The 500-claim artifact was 3,536,314 bytes;
whole-process peak RSS was 120.8 MB. This run overlapped verification, so it is not a clean
performance comparison or a worst-case authority-graph/large-PDF benchmark.

## Publication boundaries

The existing owner/remote is `alexmunzon/plan-diff`. Local coordination files, handoffs, private
paths and environment files are excluded from publication. The feature branch has an explicit
Vercel no-auto-deployment entry. Publication requires the final staged-content scan; hosted CI
and exact remote SHA are reported separately with the draft PR. No merge or deployment is
authorized. Product model execution/evaluation, human adjudication, inter-rater agreement and
real-carrier validation remain NOT RUN.
