# Release 0.1.0 notes: pre-tag sweep fixes

Decisions made while fixing the pre-tag sweep findings, without questions to Alex (subagent run,
2026-10-05). Branch `release-0.1.0`, local only. The orchestrator creates the tag.

1. **Not comparable is its own verdict.** `Verdict.NOT_COMPARABLE` covers the two disagreement
   reasons "period not comparable" and "unit not comparable" (`NOT_COMPARABLE_REASONS` in
   `models/validation.py`). The old reason "units differ" is renamed "unit not comparable".
   A copay against a coinsurance, different amounts, or different yearly allowance amounts are
   still mismatches, because there the two sources really disagree. The model refuses a result
   whose verdict does not fit its values in both directions.
2. **Accuracy.** `AccuracyRow` gains `not_comparable` (default 0, so PR 7 JSON still loads). The
   match rate stays matched over matched plus mismatched, so not comparable is left out of it.
3. **Review item.** A not comparable result gets kind `not_comparable`, severity medium
   (`config.VALIDATE_NOT_COMPARABLE_SEVERITY`, under `# Release 0.1.0`), both citations, and no
   confidence score: nothing is known to be wrong, it simply could not be checked. Never
   `pdf_cms_mismatch`.
4. **Diff.** A not comparable result on a deciding field blocks it exactly like a mismatch, so the
   flag is undecided, never a confident no. The review text says "cannot be checked against CMS"
   instead of "disagrees with CMS".
5. **Accuracy labels.** `AccuracyTable` gains `plans`, `years`, `run_id`, and `as_of` (the run's
   start date as YYYY-MM-DD, so a frozen `--now` keeps the demo byte-identical). All default to
   empty, so old files still load.
6. **Version** 0.1.0 in `pyproject.toml`, `plan_diff.__version__`, and `uv.lock`. The dashboard's
   `package.json` already said 0.1.0.
7. **Network guard.** `engine/tests/conftest.py` patches `socket.socket.connect` and `connect_ex`
   for every test, raising "network is off in tests". Unix sockets (local only) stay allowed.
   httpx's MockTransport (an in-memory fake network) never opens a socket, so it still works. No
   new dependency, so no pytest-socket.
8. **H9999-004 in the demo.** It needed a 2026 plan that renews into 2027, but the crosswalk fixture
   used H9999-004 as its "new plan" row. That row now names H9999-005; H9999-004 renews (row 4
   kept, so row numbers cited by tests did not move). Landscape rows were appended for both years
   at $0.00 in Bexar. There are no PBP rows for it, so its benefit fields are "not in CMS". Its 2027
   maximum out-of-pocket cell is "$3,400 / $5,900": the rules keep the first amount at confidence
   0.6, below the 0.7 floor, so the flag is undecided with one high `shop_again_uncertain` item.
9. **Demo check.** The new e2e test runs the demo into a temp folder and compares every JSON file
   byte for byte with `dashboard/public/demo-run/`. If it fails, run `npm run demo` and commit.
10. **Example tests.** Example 1 checks all 15 values (kind, amount, unit) against hand-typed
    factory inputs and their pages; example 2 checks shop again is yes; example 4 checks the
    review item's evidence is the PDF page and the CMS file and row.
11. **Changelog.** Fragment headings use "PR 2", not "PR 02". All fragments, plus a release
    fragment, were assembled into `## 0.1.0 (2026-10-05)` in CHANGELOG.md: PRs 0 to 9, then the
    Review 1 and Review 2 fixes, then the release fixes. changelog.d/README.md says fragments are
    deleted after assembly, so they were deleted (git history keeps them). Its template now says
    "PR N" without a leading zero.

## Demo accuracy (synthetic fixtures only, run `demo`, as of 2026-10-05)

41 matched, 1 mismatch (H9999-001 2026 specialist copay, $45 PDF vs $40 CMS), 6 not comparable
(dental and OTC allowances, no CMS period yet), 42 not in CMS. Match rate 41 / 42, about 97.6%.
These numbers say nothing about real documents.

## Risks and follow-ups

- Allowances stay not comparable until the CMS period columns are read (PR 15).
- The network guard covers Python sockets only; a test that runs a subprocess that downloads would
  not be caught. None does today.
