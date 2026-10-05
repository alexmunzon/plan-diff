## PR 05: Deterministic extraction, cost-sharing fields (2026-10-05)

- New `plan_diff.extract`: reads premium, medical deductible, maximum out-of-pocket, PCP and
  specialist copays, emergency room, urgent care, inpatient stay, and outpatient surgery from a PDF,
  each with its page, method `rule`, a short snippet, and a confidence.
- Reads "$0", "$45 copay", "$1,500", "20% coinsurance", "$395 per day for days 1 to 5",
  "Not covered", and "$0 or $40". Money is an exact decimal.
- A field it cannot find or read is left out and sent to review. Two different values lower the
  confidence and go to review with every page cited (new review kind `conflicting_values`).
