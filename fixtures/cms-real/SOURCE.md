# fixtures/cms-real: real CMS rows for the Texas slice (public domain)

Small extracts of the real CMS public use files, made in PR 15 (2026-10-05) from the files pinned
in `sources/manifest.json` and unzipped with `plan-diff unzip-cms`. Each file keeps the original
header line and only the data rows for H0028-030 (Humana Gold Plus, HMO) and H5294-014 (Wellcare
Patriot Simple, HMO), byte for byte. Nothing else was changed. CMS data is a US government work in
the public domain. CI tests the real-data path with these files and never needs the full downloads.

Row numbers below are 1-based data rows of the full CMS file (the header is row 0), the same
numbers the readers put in a CMS citation. In these extracts the same rows are numbered from 1, so
a citation made from an extract names the extract's row; the committed Texas run
(`dashboard/public/texas-run/`) was made from the full files and cites the full-file rows.

| Extract | CMS zip (document_id) | Zip SHA-256 (pinned) | Retrieved | File inside the zip | Full-file rows kept |
|---|---|---|---|---|---|
| `crosswalk_2027.csv` | cms-crosswalk-2027 | `55a392afc9144475c15993885a56177867457910a9527b14dda47640fcaf1329` | 2026-10-05 | `PlanCrosswalk2027_10012026.txt` | 15, 5240 |
| `landscape_2026.csv` | cms-landscape-2026 | `75f2797b510449fc0d376bbbbeb3c129f6091a697555281559ca28e6e4b8d882` | 2026-10-05 | `CY2026_Landscape_202609/CY2026_Landscape_202609.csv` | 92 rows from 113264 to 123408 |
| `landscape_2027.csv` | cms-landscape-2027 | `0cf545fc36dbb6be8594193c311005d9125ceedf579c24b811c2addcf8daeaab` | 2026-10-05 | `CY2027_Landscape_202609.1/CY2027_Landscape_202609.csv` | 59 rows from 106878 to 116030 |
| `pbp_2026/pbp_Section_D.txt` | cms-pbp-2026 | `1720048e668f6c9e4abc47c512e537c013600de12860d28aea4f8308b5e51de4` | 2026-10-05 | `pbp_Section_D.txt` | 13, 4694 |
| `pbp_2026/pbp_b13_other_services.txt` | cms-pbp-2026 | `1720048e668f6c9e4abc47c512e537c013600de12860d28aea4f8308b5e51de4` | 2026-10-05 | `pbp_b13_other_services.txt` | 13, 4694 |
| `pbp_2026/pbp_b16_dental.txt` | cms-pbp-2026 | `1720048e668f6c9e4abc47c512e537c013600de12860d28aea4f8308b5e51de4` | 2026-10-05 | `pbp_b16_dental.txt` | 13, 4694 |
| `pbp_2026/pbp_b1a_inpat_hosp.txt` | cms-pbp-2026 | `1720048e668f6c9e4abc47c512e537c013600de12860d28aea4f8308b5e51de4` | 2026-10-05 | `pbp_b1a_inpat_hosp.txt` | 13, 4694 |
| `pbp_2026/pbp_b4_emerg_urgent.txt` | cms-pbp-2026 | `1720048e668f6c9e4abc47c512e537c013600de12860d28aea4f8308b5e51de4` | 2026-10-05 | `pbp_b4_emerg_urgent.txt` | 13, 4694 |
| `pbp_2026/pbp_b7_health_prof.txt` | cms-pbp-2026 | `1720048e668f6c9e4abc47c512e537c013600de12860d28aea4f8308b5e51de4` | 2026-10-05 | `pbp_b7_health_prof.txt` | 13, 4694 |
| `pbp_2026/pbp_b9_outpat_hosp.txt` | cms-pbp-2026 | `1720048e668f6c9e4abc47c512e537c013600de12860d28aea4f8308b5e51de4` | 2026-10-05 | `pbp_b9_outpat_hosp.txt` | 13, 4694 |
| `pbp_2026/pbp_mrx.txt` | cms-pbp-2026 | `1720048e668f6c9e4abc47c512e537c013600de12860d28aea4f8308b5e51de4` | 2026-10-05 | `pbp_mrx.txt` | 13, 4694 |
| `pbp_2026/pbp_mrx_tier.txt` | cms-pbp-2026 | `1720048e668f6c9e4abc47c512e537c013600de12860d28aea4f8308b5e51de4` | 2026-10-05 | `pbp_mrx_tier.txt` | 51, 52, 53, 54, 55 |
| `pbp_2027/pbp_Section_D.txt` | cms-pbp-2027 | `6d8430e2ecb51acf3cc8547f12dd73506aa73f0dccf034cc3c3393868576ff47` | 2026-10-05 | `pbp_Section_D.txt` | 13, 4629 |
| `pbp_2027/pbp_b13_other_services.txt` | cms-pbp-2027 | `6d8430e2ecb51acf3cc8547f12dd73506aa73f0dccf034cc3c3393868576ff47` | 2026-10-05 | `pbp_b13_other_services.txt` | 13, 4629 |
| `pbp_2027/pbp_b16_dental.txt` | cms-pbp-2027 | `6d8430e2ecb51acf3cc8547f12dd73506aa73f0dccf034cc3c3393868576ff47` | 2026-10-05 | `pbp_b16_dental.txt` | 13, 4629 |
| `pbp_2027/pbp_b1a_inpat_hosp.txt` | cms-pbp-2027 | `6d8430e2ecb51acf3cc8547f12dd73506aa73f0dccf034cc3c3393868576ff47` | 2026-10-05 | `pbp_b1a_inpat_hosp.txt` | 13, 4629 |
| `pbp_2027/pbp_b4_emerg_urgent.txt` | cms-pbp-2027 | `6d8430e2ecb51acf3cc8547f12dd73506aa73f0dccf034cc3c3393868576ff47` | 2026-10-05 | `pbp_b4_emerg_urgent.txt` | 13, 4629 |
| `pbp_2027/pbp_b7_health_prof.txt` | cms-pbp-2027 | `6d8430e2ecb51acf3cc8547f12dd73506aa73f0dccf034cc3c3393868576ff47` | 2026-10-05 | `pbp_b7_health_prof.txt` | 13, 4629 |
| `pbp_2027/pbp_b9_outpat_hosp.txt` | cms-pbp-2027 | `6d8430e2ecb51acf3cc8547f12dd73506aa73f0dccf034cc3c3393868576ff47` | 2026-10-05 | `pbp_b9_outpat_hosp.txt` | 13, 4629 |
| `pbp_2027/pbp_mrx.txt` | cms-pbp-2027 | `6d8430e2ecb51acf3cc8547f12dd73506aa73f0dccf034cc3c3393868576ff47` | 2026-10-05 | `pbp_mrx.txt` | 13, 4629 |
| `pbp_2027/pbp_mrx_tier.txt` | cms-pbp-2027 | `6d8430e2ecb51acf3cc8547f12dd73506aa73f0dccf034cc3c3393868576ff47` | 2026-10-05 | `pbp_mrx_tier.txt` | 51, 52, 53, 54, 55 |

Zip URLs: see `sources/manifest.json` (all on https://www.cms.gov/files/zip/). The crosswalk
extract keeps the run's file name `crosswalk_2027.csv` (the run looks for that name); its content
is the real tab separated text file.

The Landscape keeps one row per county, so H5294-014 has 84 rows in 2026 and 51 in 2027 (CMS
crosswalk status "Renewal Plan with SAR": a service area reduction).

