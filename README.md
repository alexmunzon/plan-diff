# plan-diff

plan-diff reads public Medicare Advantage benefit documents (the carrier's Summary of Benefits and
similar PDFs) into one standard plan record where every value cites its document and page. It
checks each value against CMS's official public benefit files and compares one plan year with the
next, raising a "shop again" flag with its reasons so a broker can see which clients to call.

## Status

v0.1.0: engine complete on synthetic documents and synthetic CMS-shaped fixtures; real Texas slice
pending (PR 15). Synthetic means made up by our own test code: the plans, carriers, and dollar
amounts are fake.

## Run it

You need Node 24 and [uv](https://docs.astral.sh/uv/) (a Python package manager).

```sh
cd engine && uv sync && cd ../dashboard && npm ci && cd ..   # install
npm run verify                                              # every check and test
npm run demo                                                # the synthetic demo run
```

## What the demo shows

`npm run demo` writes small synthetic PDFs into a temporary folder, runs the whole pipeline on
them, and copies the JSON results to `dashboard/public/demo-run/`. It prints one line per plan:

| Plan | Shop again | Why |
|---|---|---|
| H9999-001 | yes | premium up $25 a month |
| H9999-002 | yes | plan consolidated into H9999-001 (CMS crosswalk, the file saying which plan becomes which) |
| H9999-003 | yes | plan terminated (CMS crosswalk row cited) |
| H9999-004 | undecided, needs review | its 2027 maximum out-of-pocket cell shows two amounts with no label, so the value is not trusted |

The demo also shows one value that disagrees with CMS (H9999-001's specialist copay: $45 in the
PDF, $40 in CMS). It is flagged for review, never silently picked. Dental and OTC allowances are
"not comparable" because the CMS fixtures do not state a period yet; they are counted apart from
real mismatches.

The accuracy numbers in `accuracy.json` come from synthetic fixtures, not real carrier documents.
The file names its slice (plans, years), run id, and date. They say nothing yet about accuracy on
real PDFs.

## Data rules

Synthetic and public data only; carrier PDFs are never committed. Real downloads go to the
git-ignored `data/raw/` folder, only after Alex approves the exact file list.

## Not done yet

- Jev classification and agreement checks (PR 10).
- The LLM extraction fallback (PR 11). It is planned but off; nothing calls a paid API.
- The dashboard pages (PRs 12 to 14). The dashboard is a shell today.
- Real carrier documents and real CMS files for the Texas slice (PR 15).
- The full README, decision records, and screenshots (PR 16).
