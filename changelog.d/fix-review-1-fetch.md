## Fix: review 1, fetch (2026-10-05)

- `plan-diff fetch` refuses a redirect to a different host, and refuses a file that is not really a
  PDF (carrier documents) or ZIP (CMS files), so a web page is never saved or pinned.
- A file already in `data/raw/` that does not match the manifest hash is moved to `data/raw/.rejected/`
  and reported, then downloaded again.
- Leftover `.part` files are always removed, and the manifest is rewritten safely on `--pin`.
- `document_id` may use only lowercase letters, digits, and dashes.
- The PDF guard test now fails on any tracked PDF anywhere, and cannot pass if git fails.
