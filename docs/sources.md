# Sources and fetching

plan-diff reads public documents: carrier plan PDFs (Summary of Benefits, Evidence of Coverage,
Annual Notice of Change) and CMS public data files (PBP benefits, Landscape, Crosswalk). This page
explains how we get them without ever committing them.

## The manifest

`sources/manifest.json` lists every document we use. Each entry has an id, the direct download URL,
the carrier, plan, year, and document type, plus:

- `sha256`, `size_bytes`, `retrieved_at`: the file's fingerprint, size, and download date. Empty until
  the file is pinned.
- `landing_page`: the web page where a person can find the file by hand.
- `verified`: false until a person has checked that the URL serves the right document.
- `note`: where the URL came from, or "find by hand" when it cannot be worked out.

A SHA-256 hash is a 64-character fingerprint of a file's exact bytes. If even one byte changes, the
hash changes, so it proves we are reading the same file every time.

## Fetching

From the repo root:

    uv run --project engine plan-diff fetch --manifest sources/manifest.json --out data/raw

- Downloads go into `data/raw/`, which git ignores.
- It waits 5 seconds between downloads and sends a User-Agent that says what it is, to be polite
  to carrier and CMS sites. It refuses any file over 200 MB. Both limits live in `engine/src/plan_diff/config.py`.
- If the manifest has a hash and the download does not match it, the file is deleted, nothing is
  written, and the command fails, printing the expected and received hashes. A changed file could mean
  the carrier reposted it, or the URL now serves something else; either way a person looks before we use it.
- If the manifest has no hash yet, fetch refuses unless you pass `--pin`. With `--pin` it downloads
  the file and records its hash, size, and date in the manifest ("trust on first use"). Review the file,
  then commit the manifest change.
- A redirect to a different host is refused (a redirect on the same host is fine), so a link can
  never quietly hand us a file from somewhere else.
- The file must look like what the manifest says: a carrier document must start with the PDF marker
  `%PDF-`, and a CMS file with the ZIP marker. A web page (for example a login or landing page) is
  refused, nothing is written, and nothing is pinned.
- A file already in `data/raw/` that does not match the manifest hash (or has no hash to check) is
  moved to `data/raw/.rejected/` with a message, then downloaded again, so no later step reads it.
- Entries with no URL are skipped with a message.
- A `document_id` may use only lowercase letters, digits, and dashes, because it becomes the file name.
- `--only <document_id>` fetches one document.
- It never runs in CI. Tests use a fake network instead.

The first real download waits for Alex's yes on the exact file list, sources, and sizes.

## Why PDFs are never committed

Carrier PDFs are public but copyrighted, and they are large (an Evidence of Coverage can run 300 pages).
Committing them would republish someone else's work and bloat the repo forever, since git keeps every
version. Instead the repo commits the manifest (where each file lives and its fingerprint) and the
values we extract, each with a page citation. Anyone can rebuild `data/raw/` with `plan-diff fetch`
and the hash check proves they got the same files. A test fails if any `.pdf` at all is
tracked by git; test PDFs are generated into a temporary folder each run.
