# Changelog fragments

Each PR adds one fragment file here instead of editing CHANGELOG.md. This stops parallel PRs from
fighting over the same lines in one file.

- One fragment file per PR, named `pr-NN-short-name.md` (for example `pr-03-sbc-reader.md`).
- Start it with a heading `## PR N: Short title (YYYY-MM-DD)` (the PR number without a leading zero, for example `## PR 2`), then a few plain-language bullets.
- At release, the fragments are assembled into CHANGELOG.md in PR order and then deleted from here.
