## Offline integration CLI (2026-10-07)

- Add `plan-diff integration pin` to freeze explicit synthetic enrollment evidence and the complete saved Plan Diff artifact inventory. `integration worklist` consumes those saved pins and a Bob packet, refusing changed bytes or inventory.
- Preserve native plan citations, review reasons, missing coverage, unresolved identities, and unsupported claims. Integration commands require explicit agency and producer IDs and synthetic labeling; every worklist item requires review.
- Publish complete canonical JSON atomically without replacing existing output. Add concrete cross-repository command examples and focused deterministic, malformed-input, stale-pin, and publication-failure tests.
