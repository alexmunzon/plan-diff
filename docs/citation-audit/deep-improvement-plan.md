# Deferred post-build improvement plan

Baseline: 40baca72515006e88d41f21050329fa39d37e60b, draft PR 18, local and hosted full
verification passing. This pass is distinct from the earlier build reflection. Preserve that
commit, all earlier first failures and frozen labels. All existing cases are exposed regressions.

## Ranked findings and selected scope

1. High impact/high likelihood: unexplained free-text wording can still receive support. An
   ordinary geographic promise (`nationwide`) is ignored. Selected: require bounded recognized
   wording coverage; unexplained text must go to review instead of extending a blacklist.
2. High impact/medium-high likelihood: conditions can be swapped between benefit clauses.
   Selected as the same repair: bind each condition and unit to its own named benefit clause.
3. High impact/medium likelihood: an explicit prose date can differ from typed as_of within
   the same year. Selected: consume only the matching declared date; other date wording abstains.
4. High impact/plausible accidental mismatch: the actual dashboard accepted changed text and
   typed amounts with the retained manifest. Adjudication accepted five malformed/changed
   pairs and created a revision in each. Selected: exact emitted-byte binding and completion
   validation before either consumer acts. A hash detects inconsistent bytes; it cannot
   authenticate someone who can replace both files. The reviewer wrote acceptance first.

The claim reviewer saved six fixed probe inputs and expected reasons before running them.
Baseline outcome: three false supports and three useful supported positives. Exact evidence
is in deep-21-claim-plan.json and deep-21-claim-first-results.json; v10 freezes these inputs.

## Acceptance decided before implementation

- All three new negative claims become needs_human_review; all three paired positives stay
  supported. Reasons identify unexplained wording, misplaced conditions or date mismatch.
- Original 106 default-policy cases and 77 legacy cases retain their frozen expectations;
  the eight-claim demo remains useful. No evaluation gate or label is relaxed.
- Conditions and units are checked per clause; unknown prose is surfaced, never rewritten.
- Compare the same bounded workload against the preserved baseline; count PDF reads and
  time the claim checks separately from PDF construction. No performance claim from suite time.
- Any selected artifact repair must accept genuine producer output and reject independent
  byte changes, missing completion metadata and inconsistent identity before UI/adjudication.
- Run targeted faults, independent bounded repair review, full verification, actual UI and
  artifact checks. Scan before feature push; verify exact remote SHA and hosted CI afterward.

Stop after the selected defects meet these criteria and one bounded repair review, or report
a concrete remaining blocker. Further ideas are ranked/deferred, not an endless new architecture.
No new dependencies, data downloads, model calls, security settings, merges or deployment.
