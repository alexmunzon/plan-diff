# Changelog fragments

Each PR adds one fragment file here instead of editing CHANGELOG.md. This stops parallel PRs from
fighting over the same lines in one file.

- One fragment file per PR, named `pr-NN-short-name.md` (for example `pr-03-sbc-reader.md`).
- Start it with a heading `## PR NN: Short title (YYYY-MM-DD)`, then a few plain-language bullets.
- At release, the fragments are assembled into CHANGELOG.md in PR order and then deleted from here.
