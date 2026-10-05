## PR 4: Synthetic PDF fixtures and document classifier (2026-10-05)

- New runtime dependencies pdfplumber (MIT) and pypdf (BSD-3); new dev dependency reportlab (BSD) to write test PDFs.
- Test helper `engine/tests/pdf_factory.py` writes a small Summary of Benefits shaped PDF for the fake plan H9999-001 at test time, with all 15 fields over 2 pages. EOC and ANOC variants change the title. Nothing generated is committed.
- New `plan_diff.classify`: reads the first pages and finds plan id, plan year, document type, and carrier, each with a confidence and a page citation.
- Missing or conflicting values (two plan ids, two years) make the document unsure and produce a review item instead of a guess.
- Classifier constants live under `# PR 4` in `config.py`, including the carrier alias table.
