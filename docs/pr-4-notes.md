# PR 4 notes: synthetic PDFs and the document classifier

## Dependencies and licenses (checked from installed package metadata, 2026-10-05)

| Package | Version | Kind | License |
|---|---|---|---|
| pdfplumber | 0.11.10 | runtime | MIT |
| pypdf | 6.19.0 | runtime | BSD-3-Clause |
| reportlab | 5.0.1 | dev only | BSD |
| pdfminer.six (via pdfplumber) | 20260107 | runtime | MIT |
| pypdfium2 (via pdfplumber) | 5.14.0 | runtime | Apache-2.0 or BSD-3-Clause |
| pillow (via pdfplumber, reportlab) | 12.3.0 | runtime | MIT-CMU |
| cryptography (via pdfminer.six) | 50.0.2 | runtime | Apache-2.0 or BSD-3-Clause |
| cffi, pycparser, charset-normalizer | | runtime | MIT-0, BSD-3-Clause, MIT |

No GPL or AGPL package. pypdfium2 ships the license texts of the PDFium build it bundles; the ICU
notices there quote GPL text only for ICU's Autoconf build scripts, which carry the Autoconf
exception. ICU itself is under the Unicode license. PyMuPDF is not used.

pypdf is added now because SPEC decision 6 names it; this PR uses it only in a test as an
independent page count check. Later PRs use it for page counts and metadata.

## Decisions

- **Where the factory lives:** `engine/tests/pdf_factory.py`, importable because pytest's
  `pythonpath` now includes `tests`. It writes into pytest's `tmp_path`, so no PDF is ever in the tree.
- **Factory shape:** a title line "carrier year title", then plan name and plan id, then the plan
  dates; a ruled two-column table with 8 fields on page 1 and 7 on page 2. It returns the page each
  field landed on, so PR 5 can check extraction page numbers. The ANOC variant also says
  "What changes from (year - 1) to (year)", like a real ANOC, to prove the title year wins.
- **Title first, then body:** the first 3 lines of page 1 are the title. If an attribute appears
  there, only title hits count (confidence 0.95); otherwise body hits on the first 3 pages count
  (confidence 0.75). This stops an EOC that says "see your Summary of Benefits" in its body, or an
  ANOC that names last year, from becoming ambiguous.
- **Unsure rule:** an attribute with no value (confidence 0.0) or two different values (0.3) makes
  the whole document UNSURE. The result then carries one `ReviewItem` of kind
  `unclassified_document` that lists every problem and cites every value seen. Plan id and year
  are filled in on the review item when they were found cleanly.
- **Plan id:** pattern `H` plus 4 digits, dash, 3 digits, matching the schema's PlanId. A trailing
  segment (H0028-030-001) is read but dropped. R and S contract prefixes are out of scope for the
  Texas MA slice.
- **Year:** 2010 to 2099, not preceded by `$`, a digit, a comma, or a period, so "$2050" or
  "2,020.00" are not years.
- **Carrier:** whole-phrase, case-insensitive match against `CARRIER_ALIASES` (Superior
  HealthPlan maps to Wellcare). Callers may pass their own alias table.
- **Confidence numbers** are fixed rule levels, not probabilities. They live in `config.py`.

## Risks and follow-ups

- Real carrier title pages may put the year or plan id beyond the first 3 lines; PR 15 should
  tune `CLASSIFY_TITLE_LINES` on real documents.
- A corrupted or password-protected PDF raises from pdfplumber; the caller (run command, PR 9)
  should catch it and send the document to review.
- A scanned PDF with no text layer classifies as UNSURE with everything missing, which is the
  intended safe outcome.
