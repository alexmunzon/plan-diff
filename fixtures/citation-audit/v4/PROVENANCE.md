# Provenance: citation audit cases v4

Everything here is synthetic. Same format, PDF generator, and rubric as v1, plus the policy 2
addendum in `../policy-2/README.md`. v4 only adds cases; earlier sets are never edited.

- `cases.json` (actor input) and `labels.json` (expected verdicts under policy 2), kept apart.
- `pdf-sha256.json`: the SHA-256 of every generated PDF.

Frozen on 2026-10-25T06:35Z, before the policy 2 code existed and before any of these cases ran
(SHA-256):

```text
250a6725560607b692849e1b46b8ba5b0c5aa7e625b4667d86d3bd1581e87ce4  cases.json
50105ea54eba262ec5a2a56fd975ddb7e1e5fdce065a8c4c73c5acb02bb91096  labels.json
```

Author: the builder (Claude Opus 5.5), split regression. q01 to q12 and q45 declare effective
dates so the positive verdicts stay measurable under policy 2; q03, q07, q08, and q11 check that
partial or missing dates go to a person. Not independent or human labels.
