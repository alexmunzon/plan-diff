# PR 13 notes: Plan comparison and Changes pages

Decisions made while building, without questions to Alex (subagent run, 2026-10-05). Branch
`pr-13-compare`, local only.

1. **Data kind is stated, not guessed.** `RunManifest.data_kind` is "synthetic" or "public", required in
   the model (no default) and set only by `plan-diff run --data-kind` (required option, no default; a
   missing or unknown value exits 2 before anything is written). The demo passes synthetic. The
   dashboard loader refuses a manifest without a valid `data_kind`, and the accuracy tile's
   "on synthetic fixtures" label now comes from it. Plan ids are no longer read for this. Old run
   folders without the field no longer load; the demo is the only committed run and was regenerated
   (byte-identical on two runs, one line added to `manifest.json`).
2. **Plan comparison** lives at `/plans/[plan]`, one static page per old plan id in the demo run
   (`dynamicParams = false`, so any other id is a 404). A tiny `/plans` page lists the plans so the nav
   entry has somewhere to go. The Overview's plan ids now link to their pages.
3. **All 15 fields always show**, in SPEC order. A field the diff does not list shows "Not found in
   either year"; a missing year shows "Not found in the document". A terminated plan has no 2027
   record, so it shows "No 2027 plan to compare: the plan is terminated." instead of an empty table.
4. **Citations** are text: "document, page N", or "CMS file X, row N" for a CMS row. A page becomes a
   link only when the run manifest's input for that document has a `url` that is https, and the link
   is that URL plus `#page=N`. The engine does not write `url` on run inputs yet, so the demo shows
   text only. Nothing links to a file in this repo. PR 14 can add the url to the run manifest.
5. **Confidence** shows only below `CONFIDENCE_FLOOR` (0.7, mirrored from the engine's
   `SHOP_AGAIN_CONFIDENCE_FLOOR`; a value at the floor is trusted). Direction is a word plus an icon
   ("Not comparable" in words). Undecided reads "Undecided, needs review" with the high review items
   as the reason, the same as the Overview.
6. **Review items** for a plan are queue items whose plan id is the plan's own id, the same rule as
   the Overview count. Kinds show as short phrases (for example "Cannot be checked against CMS").
7. **Changes page: a dense table, not bars.** No chart library is present, and a 6 by 6 table of
   counts reads fine as numbers. Counts include unchanged fields ("No change") so each plan's fields
   are counted once; the change list shows only fields that did not stay the same (15 in the demo).
8. **No new libraries.** Tables are plain HTML; icons come from lucide-react, already present.
9. **parseFloat test.** Besides the lint rule, a vitest scans every .ts and .tsx file under app,
   components, and lib and fails on `parseFloat`; another formats a 20-digit amount exactly.

## What the demo shows

- H9999-001: Yes, premium up $25 a month; premium $0.00 to $25.00 a month, Up, page 1 both years; 5 review items.
- H9999-002: Yes, "Consolidated into H9999-001"; 14 fields moved, specialist the same.
- H9999-003: Yes, terminated; no 2027 plan to compare.
- H9999-004: Undecided with the confidence reason; 2027 maximum out-of-pocket flagged "Read with confidence 0.6, below 0.7".
- Changes: 15 changed fields; Premium 1 up, 1 down, 1 no change.

## Risks and follow-ups

- The confidence floor is copied, not read from the run. If the engine's floor changes, update `lib/compare.ts`.
- Pages were checked through tests and `next build` only, not by eye in a browser at 375 and 1440.
  Wide tables scroll sideways inside their card on a phone.
- Nothing stops a run labeled public from using H9999 ids; the label is trusted as given.
