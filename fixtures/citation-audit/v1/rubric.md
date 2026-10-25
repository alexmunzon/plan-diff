# Citation audit label rubric, v1

A label says what a careful reviewer should conclude about one claim given only the case's
documents. Labels are written from this rubric and the case text, never from audit output.

## Verdicts

| Verdict | Use when |
|---|---|
| supported | Every typed part is stated exactly (value, kind, unit) by one plain row in an applicable document, the claim's words say nothing the parts do not carry, and no other applicable evidence disagrees. |
| contradicted | An applicable, cleanly readable cited row states a different value or a different kind of cost (copay versus coinsurance, an amount versus not covered). For a compound claim, any contradicted part. |
| conflicting_evidence | Applicable evidence disagrees with itself (two documents, or a document and the run's recorded CMS value) and nothing explicit says which controls. The verdict must not depend on which side was cited. |
| inapplicable_version | The cited evidence belongs to another plan, another plan year, another plan's booklet pages, or a version that declared dates or explicit supersession exclude. |
| insufficient_evidence | The cited location does not hold the evidence: no such page, no such row, a quote not on the page, a quote that is not the checked row, a stated condition missing, or no citation at all. Missing is never zero. |
| unverifiable | The source cannot be checked: not part of the run, missing file, bytes that differ from the recorded hash, or a file that cannot be opened. |
| needs_human_review | The evidence might support the claim, but only a person can tell: qualifying wording (negation, exception, sharing, network, eligibility, footnote) in or around the row, two or more amounts, two candidate rows, units that are not comparable, unknown document applicability, an Annual Notice of Change, a claim with no typed value, or claim words that say more than its typed parts. |

## Compound claims

Every part gets its own label when a case lists `parts`. The claim is supported only when every
part is. Otherwise the claim takes the first of: contradicted, conflicting_evidence,
inapplicable_version, unverifiable, insufficient_evidence, needs_human_review.

## Hard safety failures (defined before the first run)

1. Any claim labeled other than supported that the audit marks supported (false supported).
2. Any case in the manifest missing from the results, or a summary that does not recompute from
   the per-case rows.
3. Any audit output that changes a deterministic extracted value or rewrites the claim.

## Usefulness floor (defined before the first run)

- Recall on labeled supported claims of at least 0.8 (abstaining on everything fails).
- Exact verdict agreement of at least 0.8 over the dev and regression splits.

## Splits and independence

- dev and regression: written by the builder (Claude Opus 5.5, coordinator) on 2026-10-24
  after a first draft of the audit code existed and before any case was run through it. Not
  independent labels and not a holdout.
- challenge: twelve cases proposed by the Astra design reviewer (gpt-6-astra, an AI system, not a
  human labeler) in run 20261024-224221, with its expected verdicts copied as proposed. Their
  first results are kept as recorded; after any fix they count as regression evidence only.
- No human adjudication or inter-rater agreement has been performed.
