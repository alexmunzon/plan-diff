## PR 02: Sources manifest and fetch (2026-10-05)

- Added `sources/manifest.json` with 17 entries for the Texas slice: CMS PBP, Landscape, and Crosswalk
  files, plus Humana H0028-030 and Wellcare H5294-014 documents for 2026 and 2027. None is pinned or verified yet.
- Added `plan-diff fetch`: slow, hash-checked downloads into git-ignored `data/raw/`. A hash mismatch is
  refused and nothing is written. Files with no hash need `--pin`. Refuses files over 200 MB and never runs in CI.
- Added a test that fails if any PDF outside `tests/` is tracked by git.
- The sources manifest model now allows a missing URL (with a note), CMS files with no plan id, a landing page, and a verified flag.
