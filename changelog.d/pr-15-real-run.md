## PR 15: First run on real Texas documents (2026-10-05)

- The 17 approved files (12 carrier PDFs, 5 CMS zips) are pinned in `sources/manifest.json` with URL, SHA-256, size, and download date. No PDF or full CMS file is committed.
- CMS column names were checked against the real 2026 and 2027 files and fixed as data in `cms/layouts.py`. The readers now read coinsurance plans, copay ranges (never forced into one number), and the dental and OTC period, including OTC allowances CMS files as a shared card.
- The classifier reads the plan id forms the real Wellcare documents use. A booklet that covers several plans is read only on the requested plan's pages.
- Extraction rules were tuned to the real Summary of Benefits layouts, each rule tested on a short real snippet. An Annual Notice of Change row that shows last year and next year side by side is never read.
- Small real CMS extracts for the two plans are in `fixtures/cms-real/` so CI tests the real-data path without downloading.
- The dashboard has a second run, "Texas 2026 to 2027 (public)", under `/texas`. The synthetic demo stays the default. Carrier citations link to the carrier's own https file.
- First real results (Humana H0028-030 and Wellcare H5294-014, 2026 vs 2027, as of 2026-10-05): both plans should shop again. Of 60 values, 48 match CMS, 0 disagree, 2 cannot be checked (CMS gives a range), 10 were not found in the documents.
