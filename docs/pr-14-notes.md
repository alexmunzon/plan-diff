# PR 14 notes: Trust page and Documents view

Decisions made while building, without questions to Alex (subagent run, 2026-10-05). Branch
`pr-14-trust`, local only.

1. **Source URL by hash, not by name.** `plan-diff run --sources sources/manifest.json` (optional)
   maps every pinned entry whose URL is https to its SHA-256. A PDF whose hash equals a pinned hash
   gets that URL as `source_url` in the run manifest. `fetch` refuses a file whose hash differs from
   the manifest, so a matching hash proves where the file came from. http URLs, unpinned entries,
   CMS files, and the synthetic demo PDFs get `null`. The model also refuses a non-https
   `source_url`. Without `--sources` every URL is null; PR 15's real run must pass it.
2. **Page count** comes from pypdf when the PDF opens, else null ("Not known" on the page).
3. **Run config in the manifest.** New required `config` block: `confidence_floor` (0.7, a score,
   so a JSON number) and the three shop-again thresholds as decimal text (money rule). The
   dashboard loader refuses a manifest without it or with a floor that is not a number from 0 to 1,
   and `lowConfidence` now takes the floor from `manifest.config`. The hard-coded
   `CONFIDENCE_FLOOR` is gone (closes the PR 13 risk). PR 13's unused `url` input field is renamed
   to the engine's `source_url`.
4. **Demo regenerated.** Only `manifest.json` changed (page_count, source_url, config). Two runs of
   `npm run demo` gave byte-identical files; the e2e byte-compare test passes.
5. **Trust page.** Labels on top: data kind (from the manifest), slice (plans and years from
   accuracy.json), as of date and run id, and the floor the run used. Match rate is shown as
   "97.6% (41 of 42)", computed from the integer counts over matched plus mismatched only;
   "No comparable values" when both are zero. Not comparable is its own column. Mismatches come
   from `validation.json` verdict `mismatch`, each with both values, the PDF citation, and the CMS
   file and row, and "Neither value is picked". The queue is grouped high, medium, low, then by
   kind, each kind with one plain sentence (`REVIEW_EXPLANATIONS` in `lib/trust.ts`).
6. **Documents page.** One card per PDF input: id, carrier and plan name (from the plan records
   that list the document), plan id, year, type, page count, full SHA-256, status for documents
   that were not used, and each value cited from it ("Specialist visit, page 1") in field order.
   With an https `source_url`: an "Open the carrier's page" link for the document and one per
   value with `#page=N`, `target="_blank"`, `rel="noopener noreferrer"`. Without one: the synthetic
   note for a synthetic run, or "No carrier link recorded for this file; it is not stored in the
   repo" for a public run, so a public file is never called synthetic.
7. **Loader** now also reads `validation.json` and `plans/*.json` (both optional in `RunFiles`, so
   the PR 12 call shape still parses). Money in both is checked as text.
8. **No-PDF-link test** renders every page component (Overview, every plan, Changes, Trust,
   Documents) to static HTML with source URLs set to a site path and one https URL, and checks no
   href is a `.pdf` path on this site and every outside link is https. It renders components, not
   the `.next` folder, because vitest runs before `next build` in `npm run verify`.
9. No new libraries. Tables are plain HTML.

## What the demo shows

- Trust: synthetic, plans H9999-001 to 004, years 2026 and 2027, as of 2026-10-05, floor 0.7.
  All fields 41 matched, 1 mismatched, 6 not comparable, 42 not in CMS, 97.6% (41 of 42).
  One disagreement: specialist visit, H9999-001 2026, PDF $45.00 (H9999-001_2026_SB, page 1)
  vs CMS $40.00 (CMS file pbp_b7_health_prof.txt, row 1). Queue of 10: high 1 (cannot decide
  shop again), medium 1 document not identified, 1 PDF and CMS disagree, 6 cannot be checked
  against CMS; low 1 two values in one cell.
- Documents: 7 synthetic SBs, each with the synthetic note and no link; the unlabeled SB says it
  was not identified and no values were used.

## Risks and follow-ups

- `--sources` is opt-in. A real run without it shows no carrier links (safe, but less useful).
- `#page=N` works in browsers' built-in PDF viewers; a carrier site that serves an HTML wrapper
  ignores it.
- Pages were checked through tests and `next build`, not by eye at 375 and 1440 wide.
- Size: about 780 changed lines (lockfiles and demo JSON excluded), over the 400 line target. The
  brief said not to split; about 220 are tests and 65 are these notes and the changelog.
