## PR 16: Keep the required option check stable with colored output (2026-10-05)

- Strip terminal color codes before checking that a missing `--data-kind` produces the expected usage error.
- Exercise the assertion with color enabled while retaining the exit-code and option-name checks.
