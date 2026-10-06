# Documentation index

Start at the [root README](../README.md) for the demo walkthrough, locked setup, architecture, and
scope. These documents support asynchronous review without requiring a live presentation.

## Current contracts and evidence

- [SPEC](../SPEC.md): product intent, processing stages, and trust invariants. Planned features are
  not proof of shipped behavior; use the README for the current demo scope.
- [Canonical schema](schema.md): values, decimal money, citations, uncertainty, and run outputs
- [CMS field mapping](cms-fields.md): reference columns and comparable units
- [Sources and fetching](sources.md): pinned public sources, download approval, and raw-file policy
- [Public Texas methods](pr-15-notes.md): source-specific tuning, manual checks, and limitations
- [Safety review](../changelog.d/audit-20261005-safety.md): bounded run-folder and evidence safeguards
- [Contributing](../CONTRIBUTING.md): reproducible setup and the verification gate
- [Security](../SECURITY.md): data boundaries, private reporting, and known dependency risk

Read the Texas result as **48/48 comparable in-sample values**, alongside **10 not extracted** and
**2 not comparable**, out of 60 candidate values. There is no held-out accuracy claim. Wellcare's
shared OTC/dental/vision/hearing card is not an OTC-only balance; missing Part D fields are not $0.

## Implementation history

`pr-*-notes.md` and `review-*-notes.md` describe the work at the time it was done. Commands, counts,
and tentative decisions in these notes can be historical; check current code and manifests before
reusing them. [Release 0.1.0 notes](release-0.1.0-notes.md) and [changelog fragments](../changelog.d/)
record shipped changes. [Architecture decisions](adr/README.md) describes the ADR convention; its
planned list is not an implemented-control checklist.
