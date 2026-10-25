# Provenance: citation audit cases v3

Everything here is synthetic. No carrier document, CMS file, PHI, or real person is involved. The
format, the PDF generator, and the label rubric are the same as v1 (`../v1/PROVENANCE.md`,
`../v1/rubric.md`). v3 only adds cases; v1 and v2 files are never edited.

- `cases.json` (actor input) and `labels.json` (expected verdicts), kept apart.
- `pdf-sha256.json`: the SHA-256 of every generated PDF, frozen like v1's.

Frozen on 2026-10-25T04:42Z, before any of these cases ran (SHA-256; a copy of both files sits
outside the repo in the Astra run folder
`20261024-233333-plan-diff-citation-audit-quality-2/label-freeze-v3-20261025T044237Z/`):

```text
8764b84eaf71789061207fb0aa979f24ade2a46398c6a3d5d35844b1ed6517b1  cases.json
3564340f283572eddfc49405c62b87973ce15d055a8a566e16af61d140c675b5  labels.json
```

Authors and splits:

- `challenge-3`, cases B1 to B6: proposed with their expected verdicts and rationales by the
  second Astra quality review (gpt-6-astra, an AI system, not a human labeler), worker
  `quality-b-engine` in run 20261024-233333 (`quality-b-engine.md`, "Suggested checks"). The
  builder (Claude Opus 5.5) copied the case and label JSON as proposed, changing only the author
  field to the same role name v2 uses. Their first exposure is
  `docs/citation-audit/evidence/eval-06-v3-added-before-fixes.json`. After the fixes they are
  regression evidence only.

No human adjudication or inter-rater agreement has been performed.
