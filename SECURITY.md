# Security

plan-diff is a read-only demonstration using synthetic fixtures and public carrier/CMS data. It is
not approved for PHI, private client records, enrollment, or production decision-making. No release
has a security-support guarantee. Review the current main branch rather than assuming old snapshots
receive fixes.

## Reporting privately

Use the repository's GitHub **Security → Report a vulnerability** option if private reporting is
enabled: [private reporting](https://github.com/alexmunzon/plan-diff/security/advisories/new).
If it is unavailable, ask [the maintainer](https://github.com/alexmunzon) for a private reporting
channel without posting exploit details, credentials, or personal data in public issues. Include the
affected commit, minimal public/synthetic reproduction, expected behavior, and possible impact.
Never send real client data to demonstrate a problem.

## Trust boundaries

- **Published snapshot:** the dashboard reads code-selected committed run folders at build time.
  Their JSON is downloadable public data. There is no client-record workflow, live source refresh,
  or public upload/mutation endpoint in this demo. Do not place private data in `dashboard/public/`.
- **Run evidence:** TypeScript checks basic JSON shape, decimal-text amounts, and file counts.
  Python's canonical models provide stronger validation. Neither layer authenticates arbitrary
  third-party run files; provenance hashes do not establish that a source is safe or correct.
- **External sources:** carrier citations open the original HTTPS PDF, not a proxy hosted here.
  Fetching is an explicitly approved local action, disabled in CI. The fetcher checks pinned hashes,
  file markers and size, and refuses cross-host redirects. First-use pinning still needs human review.
- **Local parsing:** downloaded PDFs and CMS archives are untrusted inputs to parser libraries.
  Existing archive/run-path safeguards and tests reduce specific risks; this is not a malware
  sandbox or a complete hostile-file assessment. Keep raw files and generated runs git-ignored.
- **Models and uncertainty:** committed runs have Jev/LLM calls off; CI uses replay mode. Live/record
  calls require approval. Missing values, disputed text, and non-comparable periods remain review
  items. Shop-again is a broker review flag, not coverage or suitability advice.
- **Build and deployment:** lockfiles and full-SHA CI action pins improve reproducibility. CI has
  read-only repository permissions, no persisted checkout credentials, a timeout, and cancellation
  of superseded PR runs. These do not establish hosted access controls or deployment security.

## Dependency review and known residual risk

Reviewed **2026-10-06**: [braces GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
(CVE-2026-93687) is a high-severity stack-exhaustion denial of service through deeply nested brace
patterns. The reviewed advisory affects versions through 3.0.3 and lists **no patched release**.

**Status: removed, not patched upstream.** braces is no longer installed. `dashboard/package-lock.json`
has no braces or micromatch entry, and `npm audit` reports zero findings both in full (including
development tools) and with `--omit=dev`. Before this change the bounded review found 0 production
findings and the full audit reported this one advisory through several parent nodes.

The only path was lint tooling: `eslint-config-next` → `@next/eslint-plugin-next` → `fast-glob` →
`micromatch` → braces. The plugin calls fast-glob in one place, and only when an ESLint config sets
`settings.next.rootDir` (this repo does not). An npm override (`"overrides": { "fast-glob": "$fast-glob" }`
with a `file:` dev dependency) now gives the plugin a small local stand-in, `dashboard/vendor/fast-glob-shim`,
built on Node's own `fs.globSync`. It is the same stand-in agency-intake-kit uses. It matches fast-glob
3.3.1 on the recorded ordinary patterns (wildcards, `**`, character classes, plain folders, lists) and
refuses brace or extglob patterns with a clear error instead of expanding them.
`dashboard/lib/__tests__/no-braces.test.ts` checks the lockfile, the resolution and the pattern results.
All Next lint rules still run. No package version changed; 15 packages were removed.

This stand-in is our own code, not an upstream fix. Revisit it when Next or fast-glob changes: an
`eslint-config-next` upgrade must keep the tests green, and if braces ships a fix, decide whether to
return to upstream fast-glob. Do not use `npm audit fix --force`. Plan Diff has no advisory watch of
its own: the weekly braces advisory workflow lives in agency-intake-kit
(`.github/workflows/braces-advisory.yml`) and fails, emailing the owner, when a patched release ships
or the advisory changes. When it fires, recheck this repo too.

The same review found no known advisories for the 44 registry-locked Python packages. Known-advisory
checks do not prove absence of unknown vulnerabilities, malicious packages, or runtime reachability.
The tracked-text credential review found no convincing credential candidate, but excluded all
environment files, binary/non-UTF-8 content, untracked files, and git history. Do not read or commit
`.env` or `.env.*` contents, or share credentials in issues, logs, fixtures, or run outputs.

Repository hosting settings, branch protection, collaborator permissions, deployed authentication
and headers, private runtime storage, hostile-file fuzzing, and a production threat model were not
assessed or changed. Recheck advisories and the final tree after dependency changes. These bounded
checks are not a security certification or a production-readiness claim.
