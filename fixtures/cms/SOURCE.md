# fixtures/cms: SYNTHETIC, not CMS data

Every file in this folder was typed by hand for PR 3 (2026-10-05). None of it was downloaded or
copied from a CMS file. Plan ids H9999-xxx and H9998-xxx are fake, and so are the organization and
plan names, counties, and dollar amounts. They exist so the readers in `engine/src/plan_diff/cms/`
can be tested in CI without any download.

The files only copy the shape of the real files: the column names, the separator, and the crosswalk
status labels. PR 15 checked those against the real 2026 and 2027 files and moved these fixtures to
the real shapes (no values changed): the crosswalk is tab separated with no segment columns and
writes NEW and TERMINATED in the empty id columns; the Landscape premium column is "Monthly
Consolidated Premium (Part C + D)", with "Part C Premium" and "Part D Coverage Indicator" added;
the outpatient table is `pbp_b9_outpat_hosp.txt`; the PBP tables gained the range, coinsurance,
and period columns the readers now read (left empty). The real rows for the Texas slice are in
`fixtures/cms-real/`. The `messy/` crosswalk keeps its comma separated, segmented shape on purpose,
so the segment rule stays tested; its test passes that layout in.

| File | Shaped like | Documentation page |
|---|---|---|
| `crosswalk_2027.csv` | Part C and D Plan Crosswalk 2027 | https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-advantagepart-d-contract-and-enrollment-data/plan-crosswalks/2027-part-cd-plan-crosswalk |
| `landscape_2026.csv` | CY2026 MA Landscape | https://www.cms.gov/medicare/coverage/prescription-drug-coverage |
| `pbp_2026/*.txt` | PBP Benefits 2026 tables | https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-advantagepart-d-contract-and-enrollment-data/benefits-data/pbp-benefits-2026 |

Crosswalk rows: H9999-001 continues; H9999-002 is consolidated into H9999-001 (SPEC example 2);
H9999-003 is terminated (SPEC example 3); H9999-004 renews (it was "new" until release 0.1.0,
which moved the new plan row to H9999-005 and added Landscape rows for H9999-004 so the demo can
show an undecided plan); H9999-005 is new; H9998-010 renews with a service area reduction. Status codes N, R, C, T are described by ResDAC:
https://resdac.org/cms-data/variables/relationship-code

`landscape_2027.csv` and `pbp_2027/` (added in PR 9, also hand-typed and synthetic) give the
surviving plan H9999-001 a 2027 row: premium $25.00 a month, specialist $45, everything else as
in 2026. They let the demo run validate both years and compare service areas.

Real filtered extracts for the Texas slice replace or join these only after the download is
approved, each with its own source URL, file name, and retrieved date.

`messy/` (added in the Review 1 fix, also hand-typed and synthetic) holds one deliberately messy
file per reader: unpadded plan numbers, "$1,234", a 3 decimal value, a negative value, "N/A",
"Not covered", a non-UTF-8 byte, S, E, and R contracts, a non-zero segment, blank ids, duplicate
PBP rows, and a terminated crosswalk row that still names a current plan id.
