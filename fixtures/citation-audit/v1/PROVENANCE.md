# Provenance: citation audit cases v1

Everything here is synthetic. No carrier document, CMS file, PHI, or real person is involved.

- `cases.json` (actor input): documents as page lines, optional evidence metadata, optional CMS
  conflicts the run would have recorded, and one claim per case. The test harness turns each
  document into a small PDF with reportlab in invariant mode at test time; no PDF is committed.
  `state` marks a document as `missing` (not written), `truncated` (bytes cut after hashing), or
  `corrupt` (not a PDF).
- `labels.json` (expected verdicts and rationale), kept apart from the input.
- `rubric.md`: how labels are assigned, the hard safety failures, and the usefulness floor.
- `pdf-sha256.json`: the SHA-256 of every generated PDF, frozen so a change in the generator or
  reportlab is noticed rather than silently changing the evidence.

Frozen before the first evaluation run (SHA-256):

```text
e564713f765a5934ad1623fe86ea140fc20fb3be8bab56f9fab876f2e2a74d86  cases.json
1df06eb4735a0a063447fcb189e7d441552c9a5530c7537ef1c645bf4fc3f38c  labels.json
```

Authors: cases d01 to d49 by the builder (Claude Opus 5.5); cases c01 to c12 proposed by the
Astra design reviewer (gpt-6-astra), adapted to this format by the builder without changing the
proposed verdicts. See rubric.md for what that does and does not establish.
