# Download approval list (PR 15, first real download)

Prepared 2026-10-05. Nothing has been downloaded. Each link below was checked with a "headers only"
request (the server says the file's size and type without sending the file). Four Humana links
reported a size of 0 to the headers request, so for those we asked for the first byte only and read
the true size from the reply; that first byte was `%`, the start of the PDF marker. As a control, a
made-up Humana file name returned 404, so a 200 from Humana really means the file exists.

Sizes are in MB (1 MB = 1,048,576 bytes).

| document_id | source organization | exact URL | size MB | type | live | redirect host | robots or terms note |
|---|---|---|---|---|---|---|---|
| cms-pbp-2026 | CMS | https://www.cms.gov/files/zip/pbp-benefits-2026.zip | 21.83 | ZIP | yes | none (stays on www.cms.gov) | cms.gov robots.txt does not block /files/. US government work, public domain. |
| cms-pbp-2027 | CMS | https://www.cms.gov/files/zip/pbp-benefits-2027.zip | 22.29 | ZIP | yes | none | same as above |
| cms-landscape-2026 | CMS | https://www.cms.gov/files/zip/cy2026-landscape-202609.zip | 12.94 | ZIP | yes | none | same as above |
| cms-landscape-2027 | CMS | https://www.cms.gov/files/zip/cy2027-landscape-202609-1.zip | 11.41 | ZIP | yes | none | same as above |
| cms-crosswalk-2027 | CMS | https://www.cms.gov/files/zip/plan-crosswalk-2027.zip | 0.64 | ZIP | yes | none | same as above |
| humana-h0028-030-sb-2026 | Humana | https://assets.humana.com/is/content/humana/H0028030000SB26pdf | 10.71 | PDF | yes | none (stays on assets.humana.com) | assets.humana.com has no robots.txt (404). humana.com robots.txt blocks only login, quote, and secured paths. Terms of use page did not load for the reader tool, so its wording on automated download is unverified. |
| humana-h0028-030-eoc-2026 | Humana | https://assets.humana.com/is/content/humana/H0028030000EOC26pdf | 6.06 | PDF | yes | none | same as above |
| humana-h0028-030-anoc-2026 | Humana | https://assets.humana.com/is/content/humana/H0028030000ANOC26pdf | 4.93 | PDF | yes | none | same as above |
| humana-h0028-030-sb-2027 | Humana | https://assets.humana.com/is/content/humana/H0028030000SB27pdf | 10.86 | PDF | yes | none | same as above |
| humana-h0028-030-eoc-2027 | Humana | https://assets.humana.com/is/content/humana/H0028030000EOC27pdf | 3.46 | PDF | yes | none | same as above |
| humana-h0028-030-anoc-2027 | Humana | https://assets.humana.com/is/content/humana/H0028030000ANOC27pdf | 6.49 | PDF | yes | none | same as above |
| wellcare-h5294-014-sb-2026 | Wellcare (Superior HealthPlan) | https://wellcare.superiorhealthplan.com/content/dam/centene/medicare/pdfs/aep/2026/sb/H5294_2026_TX_SB_HMAO_4626794ENG_M.pdf | 0.76 | PDF | yes | none (stays on wellcare.superiorhealthplan.com) | robots.txt blocks nothing. Terms of use not checked. |
| wellcare-h5294-014-eoc-2026 | Wellcare (Superior HealthPlan) | https://wellcare.superiorhealthplan.com/content/dam/centene/medicare/pdfs/aep/2026/eoc/H5294_014_2026_TX_EOC_HMAO_4608938ENG_C.pdf | 1.65 | PDF | yes | none | same as above |
| wellcare-h5294-014-anoc-2026 | Wellcare (Superior HealthPlan) | https://wellcare.superiorhealthplan.com/content/dam/centene/medicare/pdfs/aep/2026/anoc/H5294_014_2026_TX_ANOC_HMAO_4608633ENG_M.pdf | 0.15 | PDF | yes | none | same as above |
| wellcare-h5294-014-sb-2027 | Wellcare (Superior HealthPlan) | https://wellcare.superiorhealthplan.com/content/dam/centene/medicare/pdfs/aep/2027/sb/H5294_014_2027_TX_SB_HMAO_7017524ENG_M.pdf | 0.40 | PDF | yes | none | same as above |
| wellcare-h5294-014-eoc-2027 | Wellcare (Superior HealthPlan) | https://wellcare.superiorhealthplan.com/content/dam/centene/medicare/pdfs/aep/2027/eoc/H5294_014_2027_TX_EOC_HMAO_7001688ENG_C.pdf | 1.57 | PDF | yes | none | same as above |
| wellcare-h5294-014-anoc-2027 | Wellcare (Superior HealthPlan) | https://wellcare.superiorhealthplan.com/content/dam/centene/medicare/pdfs/aep/2027/anoc/H5294_014_2027_TX_ANOC_HMAO_7002248ENG_M.pdf | 0.14 | PDF | yes | none | same as above |

Where the links came from: CMS links from each CMS landing page's Downloads section. Humana links
follow Humana's plan ID pattern. Wellcare links are listed on
https://wellcare.superiorhealthplan.com/plan-benefit-materials.html under "Wellcare Patriot Simple (HMO) H5294-014".

## Totals

- **17 files**, **116.31 MB** in all (121,956,575 bytes).
- CMS: 5 ZIPs, 69.11 MB. Humana: 6 PDFs, 42.51 MB. Wellcare: 6 PDFs, 4.67 MB.

## Things to know before saying yes

- **No redirects at all.** Every link answered directly from its own host, so fetch's "no
  cross-host redirect" rule will not block anything.
- **Size cap is fine.** fetch refuses any single file over 200 MB. The largest file is the 2027 PBP
  ZIP at 22.29 MB, about 11 percent of the cap.
- **Manifest needs updating first.** The manifest still has no URL for the two Landscapes, the
  Crosswalk, and five Wellcare documents, so fetch would skip them. The URLs in the table above
  should go into `sources/manifest.json` before the download.
- **Wellcare 2026 Summary of Benefits covers several plans.** Its file name has no plan number
  (`H5294_2026_TX_SB_...`), so it is one booklet for several H5294 plans. The parser must find the
  H5294-014 column or section inside it. The 2027 one is plan specific.
- **Humana 2027 EOC is about half the size of 2026** (3.46 MB vs 6.06 MB). Size depends on images
  and fonts as much as pages, so this is likely fine, but check the page count after download.
- **Wellcare 2027 file links were read by a summarizing tool**, then each was confirmed live as a
  PDF with H5294_014 and 2027 in its name. A person should still open one to confirm it is the right plan.

## Recommended year pair

**2026 vs 2027.** All twelve carrier PDFs for both years are live, and CMS has posted PBP and
Landscape for both years plus the 2027 Crosswalk. The SPEC fallback (2025 vs 2026) is not needed.

## What fetch will do

When Alex says yes, `plan-diff fetch --pin` downloads one file at a time and waits 5 seconds
between files, with a User-Agent that says what it is. On this first download it records each
file's SHA-256 fingerprint (a 64-character code that changes if even one byte of the file changes),
size, and date in the manifest, so every later download is checked against it. It refuses any file
over 200 MB, any redirect to a different host, and anything that does not start like a real PDF or
ZIP. Files are saved only in `data/raw/`, which git ignores, so they are never committed; only the
manifest with the fingerprints is.
