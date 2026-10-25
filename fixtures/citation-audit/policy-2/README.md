# Policy 2 expectations: unknown effective dates go to a person

Decided by Alex on 2026-10-25. Until then the audit let a document whose effective dates were
unknown support or contradict a claim when its plan and year matched (policy 1). The build spec
says unknown applicability goes to a person, and Alex chose that reading.

## Rubric addendum (applies on top of `../v1/rubric.md`)

A document's effective dates cover a claim when the claim's as-of date lies inside both declared
dates, or, with no as-of date, when the declared dates cover the whole plan year (January 1 to
December 31). A date that is not declared is unknown; it is never assumed.

- A cited source whose document's dates do not cover the claim cannot be supported or
  contradicted: it becomes needs_human_review. Declared dates that exclude the claim stay
  inapplicable_version, as before.
- Failures that do not depend on dates keep their verdict: a missing row, page, quote, or stated
  condition is still insufficient_evidence; a source that cannot be checked is still
  unverifiable; another plan or year is still inapplicable_version.
- An uncited row that reads differently in a document whose dates do not cover the claim is
  unclear evidence: it blocks support but cannot make a conflict.

## Files

- `expectations.json`: for each v1 to v3 case whose expected verdict changes under this
  policy, the new expected verdict (and part verdicts) with a one-line reason. Written by the
  builder (Claude Opus 5.5) from the rubric addendum and the case inputs alone, before the policy
  was implemented. The original `labels.json` files are frozen and unchanged; they remain the
  expectations for policy 1, which the evaluation still scores as a separate lane.
- `../v4/`: thirteen builder-written cases with declared dates, so supported, contradicted, and
  conflicting results stay measurable under this policy (otherwise sending everything to a
  person would look perfect).

Frozen on 2026-10-25T06:35Z, before the policy 2 code existed (SHA-256):

```text
4a21d3029d73e27df0bc86a99f2b4f3fd742064693385defa4035c508f329e22  expectations.json
```

These are builder-written expectations, not independent or human labels.
