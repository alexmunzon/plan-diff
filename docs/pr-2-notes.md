# PR 2 notes: sources manifest and fetch

Decisions made while building, so a reviewer can check them.

- **Model changes to SourceDocument (from PR 1).** The brief needs entries with no URL and CMS files that
  cover every plan, which the PR 1 model refused. Changes, all additive: `url` may be null (then a `note`
  is required and the entry cannot be pinned); `plan_id` may be null only for the new CMS document types;
  new optional `landing_page`, `verified` (default false), and `note`. DocumentType gains `CMS_PBP`,
  `CMS_LANDSCAPE`, `CMS_CROSSWALK`.
- **`url` means a direct file link, never a landing page.** Fetching a landing page would save HTML under a
  `.pdf` name. Where research gave only a landing page (Landscape 2026 and 2027, Crosswalk 2027), `url` is
  null with "find by hand" and `landing_page` holds the page.
- **Humana URLs** are built from the pattern in the research file. Only the 2026 ANOC was confirmed live.
- **Wellcare H5294-014:** only the 2026 EOC URL is known (from research). The other five are null.
- **File names in data/raw** are `<document_id>.pdf`, or `.zip` for CMS files, so names are stable and readable.
- **Already have it:** a pinned file already in `data/raw` with the right hash is not downloaded again.
- **Order of checks:** no URL is skipped; no hash without `--pin` is refused before any request; the
  `Content-Length` header is checked first, then the streamed byte count, so an oversized file stops early.
- **Delay:** 5 seconds before every request except the first. Skipped and refused entries do not wait.
- **CI guard:** the CLI refuses when the `CI` variable is set. The function underneath takes an injected
  client, which is how the tests run with a fake transport.
- **Manifest rewrite on `--pin`:** the whole file is rewritten from the model, keeping entry order.
- **PDF guard test** uses `git ls-files` and allows `.pdf` only under a `tests/` folder (SPEC example 7).
  It also checks `git check-ignore` covers `data/raw/`.

Risks:
- CMS ZIP sizes are unknown. If a PBP ZIP is over 200 MB the guard refuses it; raise `FETCH_MAX_BYTES` with Alex's yes.
- Humana 2027 pattern URLs are not confirmed live; a wrong URL fails with an HTTP error, which is safe.
- Trust on first use only proves the file did not change later. A person still checks the first download.
