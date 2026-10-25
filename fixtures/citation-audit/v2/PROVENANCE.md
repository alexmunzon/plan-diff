# Provenance: citation audit cases v2

Everything here is synthetic. No carrier document, CMS file, PHI, or real person is involved. The
format, the PDF generator, and the label rubric are the same as v1 (`../v1/PROVENANCE.md`,
`../v1/rubric.md`). v2 only adds cases; v1 files are never edited.

- `cases.json` (actor input) and `labels.json` (expected verdicts), kept apart.
- `pdf-sha256.json`: the SHA-256 of every generated PDF, frozen like v1's.

Frozen on 2026-10-25T04:21Z, before any of these cases ran in the evaluation harness (SHA-256;
a copy of both files sits outside the repo in the Astra run folder
`20261024-230640-plan-diff-citation-audit-quality/label-freeze-v2-20261025T042128Z/`):

```text
a25a6e631a0dc8b58e2dfb0994b18301861fb14232e1e804adf1ef8155840ae9  cases.json
76820755a8c20630a984fc919b5f4501712dd23d4cbf868e30b5d07ec390cd6a  labels.json
```

Authors and splits:

- `challenge-2`, cases A1 to A6: proposed with their expected verdicts by the Astra quality
  reviewer (gpt-6-astra, an AI system, not a human labeler) in run 20261024-230640
  (`quality-a.md`, "Suggested checks"). The builder (Claude Opus 5.5) copied them into this format
  without changing a verdict and wrote the one-line rationales. Their first exposure was a
  standalone script before this harness existed, kept as
  `docs/citation-audit/evidence/eval-03-astra-quality-cases-first-exposure.json` (all six came out
  supported, that is, false supported). After the fixes they are regression evidence only.
- `regression`, cases p01, p02, p04, p07: written by the builder from the same rubric. Each is a
  plain-wording copy of challenge case c01, c02, c04, or c07, so the claim's own words no longer
  block support and only the page safeguard (negation, exception, sharing, footnote) can.

No human adjudication or inter-rater agreement has been performed.
