# Deferred post-build review: improved

This is the separately requested deeper pass after the five build checkpoints, starting from
passing commit `40baca72515006e88d41f21050329fa39d37e60b`. The original build reflection and
failed receipts remain. The [preimplementation plan](deep-improvement-plan.md) defined the
selected scope and acceptance before repairs. No model evaluation or real-carrier validation
is implied by the development reviews.

## Consequential findings and measured changes

| Finding, ranked by impact and plausible occurrence | Before | After |
|---|---|---|
| High: extra substantive wording, such as a geographic promise | `nationwide` was falsely supported | Unrecognized wording requires review |
| High: conditions associated with the wrong benefit | Swapped conditions were falsely supported; first repair also accepted a specialist condition added to hospital care | Conditions are consumed only within their own benefit clause; both failures require review |
| High: explicit date disagrees with typed as-of date within the same year | December wording with March context was supported | Explicit date must match the declared date |
| High: audit bytes replaced while retaining the original manifest | Actual dashboard accepted changed text and amount, both still supported | Both changes refused before display |
| High, lower occurrence: malformed completion metadata accepted for adjudication | Five malformed/changed pairs each created a revision | All five refuse; no revision is created |
| Medium: valid wording rejected by the first repair | Leading date plus verified plan name and explicit typed network abstained | Both positives supported; extra conflicting unit still abstains |

The initial three negative/positive pairs changed from three false supports plus three useful
supports to three reviews plus three useful supports. The bounded repair review added four
predeclared cases and exposed one further false support and two unnecessary abstentions.
Final independent reconciliation passes all ten: five supported positives and five reviews.
This is a comparison of the same constructed inputs, not an inference from rising test counts.

Source behavior stays deterministic and bounded: declared clauses, typed amounts, payment kinds,
units, conditions and network wording; matching as-of dates; a narrowly verified identity prefix.
Unknown wording abstains. The existing extraction, applicability, supersession and conflict graph
remains. No dependency, model adapter, retrieval system or orchestration framework was added.

Completion manifest v2 fingerprints the exact emitted UTF-8 audit bytes. The producer serializes
once and writes completion last. Dashboard and adjudication require version, complete status,
matching audit identity and digest. Current readers refuse legacy v1 output with regeneration
guidance. Historical v1 evidence is unchanged. A digest detects inconsistency relative to a
retained manifest; it does not authenticate jointly replaced files.

## Verification and evidence

- [Eval-24](evidence/eval-24-deep-final.json): **116/116** exposed cases agree with frozen
  expectations, **0/106** negative cases falsely supported, **10/10** positive cases supported,
  **71/116** abstain, all **9 controls** caught. Original policy-1 lane remains **77/77**.
- [Full verification receipt](evidence/verification-24-deep-final.json): **683 engine tests,
  1 skipped; 175 dashboard tests in 18 files**; Ruff lint/format, mypy, ESLint, route generation,
  TypeScript and production build with 21 pages pass. Required gates were not weakened.
- [Final wording reconciliation](evidence/deep-24-claim-reconciliation.json) inspected full
  traces on stable source. The first reconciliation attempt detected concurrent formatting and
  correctly withheld a pass; its [failure receipt](evidence/deep-24-reconciliation-first-attempt-failure.json)
  is retained. No audit verdict was inferred from that unsuccessful attempt.
- Independent artifact review accepted a genuine v2 pair and two chained revisions with inputs
  unchanged, and rejected CRLF-only corruption and an omitted version before any revision
  directory existed. See [engine](evidence/deep-22-artifact-review-engine-receipt.json) and
  [dashboard](evidence/deep-22-artifact-review-dashboard-receipt.json) receipts. Existing structural
  fault tests deliberately rebind synthetic bytes so their semantic gates still execute.
- [Browser receipt](evidence/browser-24-deep-final.json): hidden in-app production UI validated
  supported quote/page/hash, conflict filtering, keyboard activation, compound part verdicts,
  human review and the public run's explicit no-audit state. At 390 x 844, document width was
  390 with no horizontal page overflow; captured warning/error logs were empty. No Chrome focus
  was taken. Both JSON endpoints returned 200 and exact expected bytes. OS download completion
  remains unconfirmed from the earlier browser automation timeout; it was not retried here.

Reproduce full verification from the repository root:

```sh
UV_CACHE_DIR=/tmp/plan-diff-uv-cache UV_NO_SYNC=1 RUFF_NO_CACHE=true \
MYPY_CACHE_DIR=/tmp/plan-diff-mypy-cache PYTHONDONTWRITEBYTECODE=1 \
PYTEST_ADDOPTS='-p no:cacheprovider' PYTHONPATH=engine/src:engine/tests npm run verify
```

The final audit code hash is `1834b463eca52878cc2630424c03f5b13dace83cb8c858eb5ffd3dcced62d8db`.
Demo audit.json remains byte-identical to the passing baseline; its current manifest binds that
output and this code hash, honestly recording the baseline commit plus dirty state when generated.

## Performance, preservation and stopping decision

The fixed six-claim workload ran seven samples of 100 repetitions, with PDFs constructed once
per process. [Baseline](evidence/deep-21-benchmark-before.json) versus
[final](evidence/deep-24-benchmark-final.json): median total checking time for 600 claims changed
from **0.262 to 0.313 seconds**, approximately **+20%**, or **85 microseconds per claim**.
Text-only checking changed from 0.032 to 0.055 seconds. PDF reads remained **6 before/after**;
construction was measured separately. Final samples ranged 0.302 to 0.975 seconds on a shared
machine, so this is not an isolated performance or worst-case benchmark. The small measured
absolute cost is accepted for closing false-support paths. No speed improvement is claimed.
The original [benchmark script](evidence/deep-21-benchmark-script.txt) and fixed input plan remain
available; it reads the copied plan at `/tmp/plan-diff-deep-claim-probe-plan.json` and takes a label
and new output path. Never overwrite a retained receipt.

All 69 baseline fixture, policy, rubric and evidence files compare byte-identically. V10 and
v11 preserve new predeclared cases, labels, PDF hashes and original failures. Every case is
exposed regression evidence. The preservation review noticed stale generated code provenance
after formatting; the manifest was regenerated after source settled, and final served bytes and
code hash were verified. Local coordination and handoffs remain private.

Decision: **improved; freeze this scoped pass after publication verification**. The selected
defects meet the predeclared outcome criteria and bounded repair reviews. This is not two clean
whole-product reviews. Additional exploratory loops would create a new scope rather than prove
general correctness. Exact pushed head and hosted CI are recorded on [draft PR 18](https://github.com/alexmunzon/plan-diff/pull/18)
and in the local continuation checkpoint; local receipts above predate publication.

Remaining limits: conservative grammar can reject valid paraphrases; ten useful positives and
61% abstention are weak evidence of real-world usefulness. Human calibration, untouched holdout,
model evaluation, real-carrier generalization and large-document/authority-graph stress testing
remain unperformed. CMS contrary evidence still gives a locator and generic mismatch reason
without repeating both compared values; this moderate usability improvement was ranked below
the selected correctness repairs and deferred. The latest adjudication revision remains
unanchored by a later revision. No medical/legal guarantee, live data mutation, paid call,
security expansion, merge or deployment occurred.
