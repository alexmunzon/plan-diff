# Citation audit runbook

The citation audit answers one question per benefit claim: does the evidence it cites actually
support it? A citation that exists, a matching file hash, a plausible quote, or shared keywords
are not support. This is a document review aid. It is not coverage adjudication, clinical or legal
advice, eligibility, enrollment, or a recommendation for any person's plan.

Design decision and precedence rules: [adr/citation-audit.md](adr/citation-audit.md).

Current checkpoint: [deferred deeper review and measured improvements](citation-audit/deep-improvement-report.md),
following the passing [continuation baseline](citation-audit/continuation-report.md). This feature is not deployed.

## Reproduce it (offline, synthetic, no model calls)

From the repository root:

```bash
npm run audit-demo
```

Rebuilds the synthetic demo PDFs and run in a temp folder, refuses to continue unless the rebuilt
run's `manifest.json` and `validation.json` (the two files the audit reads and binds to) match the
committed `dashboard/public/demo-run` byte for byte, audits
`fixtures/citation-audit/demo-claims.json`, and writes `dashboard/public/demo-run-audit/`.

```bash
npm run audit-eval -- ../docs/citation-audit/evidence/eval-NN-name.json
```

Runs the 116 exposed cases (61 in `fixtures/citation-audit/v1`, 10 in `v2`, 6 in `v3`, 13 in `v4`,
4 in `v5`, 4 in `v6`, 2 in `v7`, 5 in `v8`, 1 in `v9`, 6 in `v10`, and 4 in `v11`) through
the audit, the citation-exists-only baseline, and every negative control, and scores them against
the frozen labels with the policy 2 expectations (`fixtures/citation-audit/policy-2/`) applied on
top. It also runs policy 1 on v1 to v3 against their original frozen labels alone. Refuses to overwrite an existing file. Checks each set's cases and labels against the
hashes frozen in its PROVENANCE.md and each generated PDF against `pdf-sha256.json`. Exits with
status 1 when a gate fails, any report is inconsistent, a freeze is broken, or a negative control
is not caught; the evidence file is written either way.

```bash
npm run audit-bench -- ../docs/citation-audit/evidence/bench-NN.json
```

Times 8, 100, and 500 claims (the claim limit) against the demo PDFs.

Auditing your own run (the run folder supplies each PDF's identity and hash):

```bash
uv run --project engine plan-diff audit --claims claims.json --run runs/RUN_ID --docs DOCS_DIR --out audits --audit-id NAME [--meta evidence-meta.json] [--now 2026-10-05T12:00:00+00:00]
```

Environment note from this build: in this worktree macOS marks the virtual environment's
editable-install file hidden, and Python 3.12 then skips it, so `import plan_diff` fails outside
pytest. Prefixing engine commands with `PYTHONPATH=src` (run from `engine/`) works around it.

## Inputs

- Claims (`citation-claims-v1`): each claim has its original text, plan, year, an optional as-of
  date, typed parts (benefit, value, unit, optional network and conditions), and cited sources
  (document id, 1-based physical page, optional quote, optional SHA-256, optional part ids).
  Decomposition is declared by whoever writes the claim; the audit does not split free text.
- Evidence metadata (`evidence-meta-v1`, optional): effective dates, explicit supersession, and
  printed page labels. Under policy 2 a document needs declared effective dates covering the
  claim before it can support or contradict anything. Unknown dates send otherwise usable facts
  to a person; missing or unverifiable evidence retains those explicit outcomes.
  The demo declares its dates in `fixtures/citation-audit/demo-meta.json` (each synthetic SB prints
  its own coverage period). Anything not declared is shown as unknown. Upload time is never authority.
- Limits: 500 claims, 2 MB per claims or metadata file, 50 MB per PDF, 2,000 pages in total.
  Exceeding one refuses the whole audit with a message; nothing is written. A PDF's size is
  checked before it is hashed, and its page count before any text is extracted.

## Outputs

`audits/NAME/audit.json` (sidecar) and `audits/NAME/audit_manifest.json` (status, commit and
dirty state, SHA-256 of exact emitted audit bytes, claims, metadata, run manifest, run validation, audit code, and policy,
the full command with its arguments, timestamps, PDFs and pages read, verdict counts). The audit
code hash covers the audit package and the plan_diff modules it uses to read rows, values,
booklet pages, documents, and run files (`runner.CODE_FILES`), and the manifest records the
installed pdfplumber, pdfminer.six, pypdf, and pydantic versions. Python itself, other installed
packages are not fingerprinted. Current evaluation files separately fingerprint their harness,
case builder, fixture metadata, rubric, and addendum. The dashboard shows an audit only when both the run manifest
and validation.json hashes match the run, and warns on the page when any safeguard was switched
off. The manifest is written last; a
folder without it never finished. Folders are exclusive and never inside the run.

Current completion manifests use `citation-audit-manifest-v2`; the sidecar remains
`citation-audit-v1`. Both display and adjudication require the explicit v2 version, complete
status, matching audit identity, and `hashes.audit` matching the exact audit file bytes, including
whitespace. Legacy v1 or incomplete output must be regenerated from its original inputs into a
new audit folder. Preserve the old output as historical evidence; do not add a hash to it and
call it newly verified. This checks consistency against a retained manifest, not authenticity
against someone who can replace both files.

Claim wording uses a bounded grammar: each benefit clause must carry its own declared conditions,
units and payment kind. Explicit as-of wording must match the typed date (ISO date or English
month/day/year). Unrecognized substantive wording goes to human review, including geographic
promises. A display name is recognized only in an identity prefix corroborated by the matching
plan/year PDF header. These restrictions may abstain on valid paraphrases; they are not a general
semantic proof or an automatic decomposition of prose.

Reviewer corrections: `plan_diff.audit.runner.adjudicate` adds `adjudications/0001.json`, then
`0002.json`, each naming the audit's hash and the previous revision's hash. The computed verdict
is never rewritten. Before adding a revision it checks the whole existing chain (file names,
revision numbers, parent hashes, audit hash, and each revision's claim and computed verdict) and
refuses a broken one. Nothing points at the latest revision, so an edit to it alone is not
detectable; every earlier revision is anchored by the one after it.

## Before and after on the demo run

| Claim | Citation exists (baseline) | Audit |
|---|---|---|
| Premium $25 a month in 2026, citing the 2027 SB page 1 | supported | inapplicable_version: the document is for 2027 |
| Specialist $45 a visit, citing the 2026 SB page 1 | supported | conflicting_evidence: the run recorded CMS saying $40 |
| Platinum MOOP $3,400, citing a cell reading "$3,400 / $5,900" | supported | needs_human_review: two unlabeled amounts |
| Dental $2,000, citing page 1 (the row is on page 2) | supported | insufficient_evidence: no dental row on page 1 |
| Inpatient $325 a day, quoting "days 1 to 10" | supported | insufficient_evidence: the quote is not on the page |
| Premium $0 and Tier 2 $5 (the page says $8) | supported | contradicted, with the premium part still shown as supported |
| Silver OTC $150 a year, citing the Silver SB | supported | needs_human_review: an unidentified 2026 SB gives $50 a quarter, which cannot be compared |

## Evaluation results (synthetic, deterministic lane only)

Evidence files, never overwritten (each run's first exposure is kept as recorded):

| File | Cases | Agreement | False supported | What it records |
|---|---|---|---|---|
| `eval-01-first-run.json` | 61 | 60 | 0 of 50 | first run; miss d21 |
| `eval-02-after-d21-fix.json` | 61 | 61 | 0 of 50 | one minimal fix |
| `eval-03-astra-quality-cases-first-exposure.json` | 6 | 0 | 6 of 6 | A1 to A6, standalone script |
| `eval-04-v2-added-before-fixes.json` | 71 | 65 | 6 of 60 | v2 frozen and run before fixes |
| `eval-05-after-quality-a-fixes.json` | 71 | 71 | 0 of 60 | after the first review's fixes |
| `eval-06-v3-added-before-fixes.json` | 77 | 71 | 6 of 66 | B1 to B6 frozen and run before fixes |
| `eval-07-after-quality-b-fixes.json` | 77 | 77 | 0 of 66 | after the second review's fixes |
| `eval-08-policy-2-first-run.json` | 90 | 90 reported | 0 of 86 reported | historical result; d15 expectation omitted and serialized integrity defective |
| `eval-09-policy-2-review-first-exposure.json` | 5 | 1 | 2 of 4 | supersession counterexamples and d15 before repair |
| `eval-10-after-policy2-review-fixes.json` | 94 | 94 | 0 of 89 | first continuation repair; later review exposed more failures |
| `eval-11-replacement-context-first-exposure.json` | 4 | 0 | 4 of 4 | unavailable or ambiguous replacements before repair |
| `eval-12-after-replacement-context-fixes.json` | 98 | 98 | 0 of 93 | after replacement-context repair |
| `eval-13-reflection-cycle-first-exposure.json` | 2 | 0 | 2 of 2 | circular supersession before repair |
| `eval-14-after-reflection-fixes.json` | 100 | 100 | 0 of 95 | supersession repairs; later review found wording failures |
| `review-15-decomposition-first-exposure.json` | 5 | 0 | 5 of 5 | independent wording probes before repair |
| `eval-17-after-decomposition-fixes.json` | 105 | 105 | 0 of 100 | after wording repairs; later not-covered failure retained separately |
| `review-18-not-covered-first-exposure.json` | 1 | 0 | 1 of 1 | not-covered benefit mismatch before repair |
| `eval-19-after-final-review-fixes.json` | 106 | 106 | 0 of 101 | final exposed set; all nine controls caught |

eval-08 is the first run of policy 2 (unknown effective dates go to a person) and of the 13 v4
cases, whose labels and the policy 2 expectations were frozen before the code existed. Under
policy 2 only 4 cases are expected to be supported, all in v4 and written by the builder, so
supported precision and recall (4 of 4), conflict detection (3 of 3), and the usefulness floor
rest on very few cases; 59 of 90 cases (66%) go to a person. The policy 1 lane, scored against
the original frozen labels, still agrees on 77 of 77 with 0 false supported of 66. This only
establishes agreement on those fixtures. All nine negative controls were recorded as caught, including the new one that
switches policy 2 off (d01, c12, and q03 then become falsely supported).

Those eval-08 figures are historical reported results, not corrected accuracy: review found the
missing d15 expectation and invalid sorted-JSON integrity checks for d26 and c11. Revision 2
adds d15 without changing the original expectations. The latest eval-19 has 5 supported
positives, 66/106 human-review outcomes, zero false support on 101 negative cases, and 77/77
legacy agreement. v5 to v9 are already exposed review/reflection regressions. None is untouched holdout.

All files are under `docs/citation-audit/evidence/`. In eval-07: supported precision and recall
11 of 11; 33 of 77 cases abstain (needs_human_review); baseline 18 of 77, 58 false supported of
66. Part-level false support is 0, but only 3 cases (d25, d26, c11) carry part labels, so that
check covers 3 compound claims, not every part. The file also holds a 95% Wilson interval
(0 to 5.5% for 0 of 66). The cases are a constructed and now exposed set, not a random sample,
so that interval is arithmetic on the count only. It is not a coverage guarantee for real claims.

Each AI review found cases the code then got wrong. A1 to A6 (first review) and B1 to B6 (second)
were all marked supported before their fixes. After fixes they are regression cases, not an
untouched holdout. Two review passes have each found new high-severity problems, so the audit
has not yet reached two clean passes.

Negative controls, all caught in eval-07, each for its named reason: accept any existing citation;
ignore plan and year (d45 must become conflicting_evidence); ignore effective dates (d15 must
become conflicting_evidence); remove the contradiction check; treat unknown as supported; drop a
failing case; forge the summary; flip a prediction while keeping its old scoring fields.

Benchmarks (`bench-01.json`, `bench-02-after-quality-a-fixes.json`,
`bench-03-after-quality-b-fixes.json`): 8, 100, and 500 claims took 0.15, 0.27, 0.44 seconds in
the first, and 0.14, 0.24, 0.67 seconds in the latest; each of the 7 PDFs is opened once in every
run; about 7.2 KB of output per claim at 500 claims.

What these numbers do not show: the cases were written by the builder and an AI reviewer after a
first draft of the code existed, so they are not independent labels or an untouched holdout. No
human adjudication, inter-rater agreement, model-lane accuracy, or public deployment has been
performed. Hosted CI is reported separately in the draft PR. Nothing here shows healthcare correctness in general.

## Data and label provenance

Everything is synthetic: fake plans H9999-001 to H9999-004 and a fake carrier. Case PDFs are drawn
at test time and never committed; their hashes are frozen in
`pdf-sha256.json` in each case set (v1, v2, v3). Inputs (`cases.json`) and
labels (`labels.json`) are separate files; `v1/rubric.md` defines the verdicts, the hard safety
failures, and the usefulness floor, all written before the first run. v2 and v3 add cases
without editing earlier sets; their labels were frozen before they ran. See `PROVENANCE.md` in each folder.

## Dependencies and licenses

No new dependency. Engine: pdfplumber (MIT), pypdf (BSD-3), pydantic, typer, polars as before;
reportlab (BSD) stays test-only. Dashboard: no new package; the page uses lucide-react and React
already in the lockfile.

## Limitations

- The supported verdict needs one plain table row and a page with no qualifying wording. Real
  carrier pages usually carry such wording, so most real claims will go to a person.
- Only the 15 v1 fields, in-network values, and the extractor's own row labels are covered.
- Claim wording uses narrow benefit aliases and context checks, not a comprehensive free-text
  interpretation. Reviewers must still assess broader wording and unsupported semantics.
- Applicability uses plan, year, booklet pages, Annual Notice of Change detection, and declared
  metadata only. Geography, tier eligibility, and network tiers beyond in-network are not
  modeled; claims that depend on them go to a person.
- The model lane is not implemented. Its field is always `not_run`.

## Fixed after the Astra quality reviews (2026-10-24 and 2026-10-25)

Each finding was confirmed against the code, reproduced where it changes a verdict (eval-04,
eval-06), fixed minimally, given a targeted test in `engine/tests/unit/test_citation_audit.py` or
the dashboard tests, and rechecked (eval-05, eval-07).

First review (quality-a):

- High: claim wording checked as a set of amounts (A1); a stated period dropped (A2); footnote
  markers folded into digits (A3); rows found without the extractor's drug-section rule (A4); a
  failed citation hiding its page from the contrary search (A5); uncited evidence judged by
  different applicability rules than cited evidence; a later year's replacement dismissing a
  conflict (A6).
- Medium: dashboard checks of parts, policy, and validation.json binding; only a missing folder
  means "no audit"; scorer rescoring, part-level false support as a hard failure, nonzero exit;
  adjudication chain checks; limits before work; wider code hash and full recorded command.
- Low: plain-wording cases p01, p02, p04, p07 exercise their page safeguards on their own.

Second review (quality-b-engine and quality-b-eval):

- High: amounts with no unit words in a compound claim (B1); fullwidth letters hiding "not" in
  claim text (B2); circled and subscript digits folding into amounts; a heading on an earlier page
  ("OUT-OF-NETWORK BENEFITS") governing the cited page (B3); qualified or out-of-grammar rows,
  and matching rows with restrictions, dropped from the contrary search (B4); rows in documents
  whose plan is unknown set aside instead of blocking (B5, reversing a judgment call made in the
  first round); another plan's replacement dismissing a conflict (B6); repeated amounts with an
  extra period; the evaluation not checking predicted parts against the claim; the dashboard
  showing a supported part with its evidence removed.
- Medium: incomparable units now unclear whichever side is cited; unknowns-off mutant consistent
  for uncited evidence; replacements must cover the claim's date or whole year; eval exit covers
  baseline and mutant integrity, and mutants must produce the named verdict; dashboard checks the
  policy against its recorded hash, nested document and manifest shapes, and claim lanes;
  adjudication checks each earlier revision's claim and computed verdict; fixture freezes enforced
  in the standalone evaluation; library versions recorded.
- Docs: the Wilson interval, the demo's byte-for-byte check, the code hash, and part-level
  coverage are now described as narrowly as they are implemented.

Known limits that remain:

- Two parts of one claim that share a unit (two per-visit copays) are supported only when the
  claim names each benefit with the extractor's own row wording ("primary care visits",
  "specialist visits"); "PCP visits" goes to a person.
- A heading carried from an earlier page is the last non-row line before the page; a later,
  narrower heading does not cancel it, so such claims go to a person.
- An unreadable document in the run is listed as unverifiable but its contents cannot be searched
  for contrary evidence.
- The most recent adjudication revision is not anchored by anything after it.

## Decided: unknown effective dates (policy 2)

Alex chose on 2026-10-25 that unknown effective dates go to a person (see the ADR and
`fixtures/citation-audit/policy-2/README.md`). The original frozen labels were not edited: a
separate, frozen expectations file lists the 24 cases whose expected verdict changes, and the
policy 1 lane keeps scoring the original labels. Consequence: real claims succeed only with
evidence metadata that declares effective dates.

`expectations-r2.json` separately corrects omitted d15. Original labels and expectations remain
unchanged. Rubric byte identities are now bound; this proves consistency with the recorded
snapshot, not original freeze chronology. Replacements also need readable evidence and
applicable plan/year/booklet context before they may dismiss another document.

## Portfolio statement

Plan Diff includes an offline audit of typed benefit claims against their cited pages and
declared context. The latest 106 exposed synthetic cases agree with their labels, including five
supported positives; 66 require human review. It has zero false support on 101 negative cases,
while a citation-exists baseline wrongly supports 93. Repeated independent AI reviews exposed
false-support paths, with failures preserved before repairs. This is regression evidence, not
human validation or accuracy on real carrier documents. Full local verification passes and the
production UI was checked, subject to the download-event limitation in the continuation report.
The addition is not deployed.
