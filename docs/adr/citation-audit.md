# Citation audit: does the cited evidence support the claim? (2026-10-24)

## Context

Every extracted value in Plan Diff carries a citation (document, page, method). A citation that
exists is not the same as a citation that supports a statement. A reviewer needs to see, for one
benefit claim at a time, whether the cited page in the right document and version actually says
what the claim says, and what else in the run says otherwise.

Architecture as found at fdc9ebb, and how it was reconciled with the build spec:

- Reused, not copied: `extract/values.parse_value` and `config.EXTRACT_LABELS` (the only value
  parser), the extractor's drug-section and skipped-section rules, `run/documents` PDF reading (pdfplumber), SHA-256 and PDF error handling,
  `classify/booklet.plan_pages` (multi-plan booklet pages), `validation.json` PDF/CMS mismatches
  recorded by the run, `RunManifest` inputs for each document's identity.
- Discrepancy: `Citation.page` means a PDF page or a CMS row depending on method, and
  `Citation.text` is a reconstructed snippet of at most 200 characters, not a verbatim quote. The
  audit therefore has its own `Location` (kind, page or row, printed page label) and keeps the
  row it actually read.
- Discrepancy: the source and run models have no effective dates or supersession. The audit takes
  them only from an optional evidence metadata file and records "unknown" otherwise.
- Discrepancy: `npm run demo` rebuilds `demo-run/` and a test compares it byte for byte, so the
  audit lives next to the run (`demo-run-audit/`), never inside it.

## Decision

A separate, versioned sidecar (`citation-audit-v1`) produced by `plan-diff audit`. It never
changes run outputs, extracted values, or the claim. Five separate kinds of check per cited
source and part: claim wording, citation resolution, version and context, support, and other
evidence. Each check records pass, fail, unknown, or not run, with a reason.

Verdicts: supported, contradicted, conflicting_evidence, inapplicable_version,
insufficient_evidence, unverifiable, needs_human_review.

Precedence for one cited source (first failure wins): source cannot be checked, then wrong
version or context, then location problems, then a row outside the grammar, then a different
value, then a missing condition. A contradiction or missing condition read in an unclear context
(an unknown) becomes needs_human_review.

Effective dates (policy 2, decided by Alex on 2026-10-25): a document's dates cover a claim only
when both dates are declared and contain the claim's as-of date, or the whole plan year when no
as-of date is given. A cited source whose dates do not cover the claim can neither support nor
contradict it; it becomes needs_human_review. Missing evidence (no row, page, quote, or stated
condition) stays insufficient_evidence whatever the dates. An uncited row that reads differently
in such a document blocks support but cannot make a conflict. Policy 1, used until then, let
unknown dates pass when plan and year matched; it remains only as `Policy(unknown_dates_block=
False)`, which the evaluation scores against the original frozen labels as a separate lane.

Across sources and other evidence for one part: supported plus any applicable disagreement is
conflicting_evidence, and so is a contradicting citation when another applicable row states the
claim, so the verdict does not depend on which side was cited. Other evidence is judged by the
same applicability checks as a cited source. Rows from another plan, year, or booklet's pages
are left out; rows in a version that dates or supersession exclude are shown as set aside; a
clean row stating another value in an applicable document is a conflict. Every other row that
reads differently, or that matches but carries qualifying wording (on its page or in a heading
carried from an earlier page), is unclear and blocks support (needs_human_review): an unknown
plan, an ANOC, unclear booklet pages, a row outside the grammar, or a unit that is not
comparable. A cited page counts as already checked only when its row decided that source's
verdict, so a bad citation cannot hide a conflict. Across parts of a compound claim:
support needs every part; otherwise contradicted, conflicting, inapplicable, unverifiable,
insufficient, needs review, in that order, with every part's verdict kept.

The deterministic lane is deliberately narrow. Supported means: one row for the benefit on the
cited page, starting with the extractor's label, holding exactly one value whose kind, amount, and
unit equal the claim; nothing left in the row beyond units, filler, and the claim's declared
conditions; no qualifying wording (negation, exception, sharing, network, eligibility, footnote)
on the page outside the row; claim words that say nothing the typed parts do not carry. It is not
a general semantic judge.

The model lane is a recorded `not_run` field, not an interface. No transport, adapter, or prompt
exists. Adding one needs Alex's approval of a provider, budget, and calibration plan first.

Reviewer corrections are separate numbered files (`adjudications/0001.json`, ...), each naming
the audit file hash and the previous revision hash. `audit.json` is never rewritten.

The deferred post-build review found unsupported wording and mismatched artifact bytes could
survive earlier gates. Claim checks now require bounded recognized wording, with conditions,
units and payment kinds attached to their benefit clause and an explicit as-of date equal to
the declared date. Unrecognized wording abstains. Completion manifest v2 binds the exact emitted
audit bytes; both UI and adjudication validate that binding, status and identity before acting.
V1 artifacts remain historical evidence and require regeneration into a new folder for current
use. The digest is a consistency check, not authentication of jointly replaced files.

## Consequences

- Real carrier pages often carry qualifying wording that this narrow grammar sends to a person.
  The design favors abstention over unsupported conclusions; the synthetic tests cannot guarantee
  an absence of false support on new inputs.
- Claims must be declared as typed parts. The audit does not split free text into claims.
- Labels for the evaluation are builder and AI written. No human adjudication, inter-rater
  agreement, or model evaluation has been performed.
- A replacement document dismisses another only when it is for the same plan and plan year and
  its declared dates cover the claim's date, or the whole plan year when no date is given.
- Replacement evidence must be readable and pass the shared context checks. Circular
  supersession establishes no authority order, so an edge in a cycle dismisses no evidence.
- Non-goals: coverage adjudication, eligibility, enrollment, recommendations for any person,
  retrieval or vector search, a chatbot, automatic approval, live model calls.
