## PR 9: Run command, run folder, CMS unzip, and the demo (2026-10-05)

- New `plan-diff run --docs --cms --plans --years --out --run-id [--overwrite] [--now]` reads every PDF, classifies it, extracts the 15 fields, checks them against CMS, diffs 2026 against 2027 by the crosswalk, and writes one run folder: manifest.json, plans/, plans.parquet, validation.json, accuracy.json, diff/, review_queue.jsonl.
- A run folder is never changed after it is written. Running the same run id again is refused unless you pass `--overwrite`. With `--now` the clock is frozen, so the same inputs give byte-identical files.
- A corrupt, password-protected, or unclassifiable PDF goes to the review queue; it never stops the run.
- Jev and the LLM are off in this PR. The manifest says so and shows zero calls and zero cost.
- New `plan-diff unzip-cms` unzips fetched CMS files next to the zip, refusing paths that escape the folder, symlinks, too many files, or too many bytes, and skipping a zip whose hash has not changed.
- New `npm run demo` builds synthetic PDFs in a temp folder, runs them against the synthetic CMS fixtures, and writes the JSON (no PDFs) to `dashboard/public/demo-run/`.
- SPEC examples 1 to 8 now pass end to end in `engine/tests/e2e/test_examples.py`.
