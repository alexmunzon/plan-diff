# Review 1 fixes: fetch

Decisions made while fixing the first review of `plan-diff fetch`, so a reviewer can check them.

- **Redirects.** httpx still follows redirects, but the final response host must equal the host in the
  manifest URL, or the document is refused before any byte is saved. Same-host redirects (for example
  `/a.pdf` to `/files/a.pdf`) are allowed. Only the final host is compared; a hop through another host
  that lands back on the original host is allowed, since the bytes still come from the expected host.
  Hosts are compared exactly, so `www.cms.gov` to `cms.gov` counts as a different host and is refused.
- **Content check.** After download and before the hash check, move, or pin: carrier types (SB, EOC,
  ANOC, and also OTHER, since it is saved as `.pdf`) must start with `%PDF-`; CMS types must start with
  `PK\x03\x04`. Otherwise the message names the problem ("not a PDF" or "not a ZIP"), nothing is written,
  nothing is pinned, and the exit code is 1.
- **File already at the destination.** It is re-hashed. If it matches the manifest it is kept. If it
  does not match, or the manifest has no hash to check it against (the `--pin` case), it is moved to
  `data/raw/.rejected/<name>` (replacing an older reject of the same name) and reported, then the
  download runs. If that download fails, the bad file is still gone from `data/raw/`. Quarantine was
  chosen over delete so a person can look at what was there.
- **Size guard** already counted streamed bytes; a new test proves it with a chunked body and no
  `Content-Length` header.
- **PDF guard** (SPEC example 7) is now stricter than the SPEC wording: no `.pdf` may be tracked
  anywhere, including `tests/`, because `pdf_factory` writes only to `tmp_path`. The test asserts
  `git ls-files` returned 0 and listed `SPEC.md`, so an empty or failed listing cannot pass.
- **document_id** must match `^[a-z0-9-]+$` (it becomes the file name). Defined in `models/source.py`,
  not `models/ids.py`, to stay out of the other fix branch. `Citation.document_id` is unchanged. A bad id
  fails manifest validation, so fetch stops before any request (a validation error, not a refusal line).
- **Temp files.** Every path after `_download` runs inside try/finally that removes the `.part` file
  (a no-op once it has been moved into place). The `--pin` manifest rewrite writes a temp file in the
  same folder, then `os.replace`, so a crash never leaves half a manifest.

Risks:
- Some carrier or CMS links may legitimately redirect to a CDN on another host. Those will now be
  refused; the fix is to put the final direct URL in the manifest after a person checks it.
