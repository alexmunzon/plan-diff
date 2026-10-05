## PR 13: Plan comparison and Changes pages (2026-10-05)

- New Plan comparison page per plan: the 15 fields side by side for both years, each value with its document and page, the change direction in words with an icon, the category, low confidence values called out, the crosswalk status and shop-again answer with reasons at the top, and the plan's review items.
- New Changes page: a count of fields per category and direction across plans, and a table of every field that changed.
- Plan comparison and Changes are now live in the nav; Trust and Documents follow in PR 14.
- `plan-diff run` now needs `--data-kind synthetic` or `--data-kind public`, and the run manifest records it. The dashboard reads that label instead of guessing from plan ids. The demo is labeled synthetic.
